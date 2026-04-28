"""
GCS hybrid sync for orap SQLite DBs (Cloud Run 영속성).

전략:
- 시작 시: GCS에서 모든 DB 다운로드 (users.db + 기관별 DB)
- users.db (인증/권한): 5초 폴링, 변경 감지 즉시 업로드 (write-through)
- 기관 DB (jbnu/korea/sejong 등): 30초 폴링으로 변경 감지, 60초 안정화 후
  5분 주기로 일괄 업로드 (대용량 import 중 잦은 업로드 방지)
- SIGTERM/SIGINT: 모든 dirty DB 최종 업로드 후 종료

환경변수:
- GCS_BUCKET: 버킷명 (기본 ailibrary-orap-data)
- GCS_SYNC_DISABLED=1: 로컬 개발용으로 동기화 끄기
"""

import logging
import os
import signal
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET_NAME = os.environ.get("GCS_BUCKET", "ailibrary-orap-data")
APP_DIR = Path(__file__).parent.resolve()
USERS_DB = "users.db"

CRITICAL_POLL_INTERVAL = 5      # users.db mtime 폴링 (초)
BULK_POLL_INTERVAL = 30         # 기관 DB mtime 폴링 (초)
BULK_BATCH_INTERVAL = 300       # 기관 DB 일괄 업로드 주기 (초, 5분)
BULK_STABILITY_THRESHOLD = 60   # 마지막 변경 후 N초 동안 변경 없으면 안정 (대용량 import 보호)

_client = None
_bucket = None
_last_uploaded_mtime = {}       # db_file -> mtime (마지막 업로드 시점)
_last_modified_mtime = {}       # db_file -> mtime (마지막 변경 감지 시점)
_last_modified_at = {}          # db_file -> wall time (변경 감지된 시각)
_dirty_lock = threading.Lock()
_running = False


def _get_bucket():
    global _client, _bucket
    if _bucket is None:
        from google.cloud import storage
        _client = storage.Client()
        _bucket = _client.bucket(BUCKET_NAME)
    return _bucket


def _list_known_dbs():
    """users.db에서 institutions 테이블을 읽어 동적으로 알려진 DB 파일 목록 반환."""
    dbs = {USERS_DB}
    users_path = APP_DIR / USERS_DB
    if users_path.exists():
        try:
            conn = sqlite3.connect(str(users_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='institutions'")
            if cur.fetchone():
                cur.execute("SELECT db_file FROM institutions WHERE is_active = 1")
                for (db_file,) in cur.fetchall():
                    if db_file:
                        dbs.add(db_file)
            conn.close()
        except Exception as e:
            logger.warning("[gcs_sync] _list_known_dbs failed: %s", e)
    # 기본값 (institutions 테이블 없을 때)
    for default in ("jbnu.db", "korea.db", "sejong.db"):
        dbs.add(default)
    return sorted(dbs)


def _download_one(db_file):
    """단일 DB를 GCS에서 로컬로 다운로드. 원격에 없으면 스킵."""
    blob = _get_bucket().blob(f"db/{db_file}")
    local_path = APP_DIR / db_file
    if not blob.exists():
        logger.info("[gcs_sync] no remote db/%s — keeping local", db_file)
        return False
    blob.download_to_filename(str(local_path))
    mtime = local_path.stat().st_mtime
    _last_uploaded_mtime[db_file] = mtime
    _last_modified_mtime[db_file] = mtime
    logger.info("[gcs_sync] downloaded %s (%d bytes)", db_file, local_path.stat().st_size)
    return True


def _upload_one(db_file):
    """SQLite backup API로 안전 핫복사 후 GCS 업로드."""
    local_path = APP_DIR / db_file
    if not local_path.exists():
        return
    tmp_path = APP_DIR / f".{db_file}.upload_tmp"
    try:
        src = sqlite3.connect(str(local_path))
        dst = sqlite3.connect(str(tmp_path))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        blob = _get_bucket().blob(f"db/{db_file}")
        blob.upload_from_filename(str(tmp_path))
        _last_uploaded_mtime[db_file] = local_path.stat().st_mtime
        logger.info("[gcs_sync] uploaded %s", db_file)
    except Exception as e:
        logger.error("[gcs_sync] upload %s failed: %s", db_file, e)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def startup_download():
    """앱 시작 시 알려진 모든 DB를 GCS에서 다운로드."""
    # users.db 먼저 다운로드 (institutions 테이블 읽기 위해)
    try:
        _download_one(USERS_DB)
    except Exception as e:
        logger.error("[gcs_sync] startup download users.db failed: %s", e)
    # 그 다음 기관 DB 다운로드
    for db in _list_known_dbs():
        if db == USERS_DB:
            continue
        try:
            _download_one(db)
        except Exception as e:
            logger.error("[gcs_sync] startup download %s failed: %s", db, e)


def _check_mtime(db_file):
    """파일이 존재하고 mtime이 변경됐는지 확인. (changed, mtime) 반환."""
    local_path = APP_DIR / db_file
    if not local_path.exists():
        return False, 0
    mtime = local_path.stat().st_mtime
    return mtime != _last_uploaded_mtime.get(db_file, 0), mtime


def _critical_watcher():
    """users.db 변경 감지 시 즉시 업로드 (write-through)."""
    while _running:
        try:
            changed, mtime = _check_mtime(USERS_DB)
            if changed:
                _upload_one(USERS_DB)
        except Exception as e:
            logger.error("[gcs_sync] critical watcher error: %s", e)
        time.sleep(CRITICAL_POLL_INTERVAL)


def _bulk_watcher():
    """기관 DB 변경 감지 → dirty 마크 (실제 업로드는 _bulk_uploader가 수행)."""
    while _running:
        try:
            for db in _list_known_dbs():
                if db == USERS_DB:
                    continue
                changed, mtime = _check_mtime(db)
                if changed and mtime != _last_modified_mtime.get(db, 0):
                    with _dirty_lock:
                        _last_modified_mtime[db] = mtime
                        _last_modified_at[db] = time.time()
        except Exception as e:
            logger.error("[gcs_sync] bulk watcher error: %s", e)
        time.sleep(BULK_POLL_INTERVAL)


def _bulk_uploader():
    """5분마다 dirty + 안정화된 기관 DB 일괄 업로드."""
    while _running:
        time.sleep(BULK_BATCH_INTERVAL)
        now = time.time()
        to_upload = []
        with _dirty_lock:
            for db, modified_at in list(_last_modified_at.items()):
                last_mtime = _last_modified_mtime.get(db, 0)
                if last_mtime != _last_uploaded_mtime.get(db, 0):
                    if now - modified_at >= BULK_STABILITY_THRESHOLD:
                        to_upload.append(db)
        for db in to_upload:
            _upload_one(db)


def _final_upload():
    """SIGTERM 시 호출. 모든 dirty DB 최종 업로드."""
    logger.info("[gcs_sync] final upload starting...")
    for db in _list_known_dbs():
        try:
            changed, _ = _check_mtime(db)
            if changed:
                _upload_one(db)
        except Exception as e:
            logger.error("[gcs_sync] final upload %s failed: %s", db, e)
    logger.info("[gcs_sync] final upload done")


def _shutdown_handler(signum, frame):
    global _running
    logger.warning("[gcs_sync] signal %s received — shutting down", signum)
    _running = False
    try:
        _final_upload()
    finally:
        os._exit(0)


def init():
    """앱 시작 시 호출. startup download + 백그라운드 동기화 시작."""
    global _running

    if os.environ.get("GCS_SYNC_DISABLED", "0") == "1":
        logger.info("[gcs_sync] disabled (GCS_SYNC_DISABLED=1)")
        return

    logger.info("[gcs_sync] bucket=%s app_dir=%s", BUCKET_NAME, APP_DIR)
    startup_download()

    _running = True
    threading.Thread(target=_critical_watcher, daemon=True, name="gcs-critical").start()
    threading.Thread(target=_bulk_watcher, daemon=True, name="gcs-bulk-watch").start()
    threading.Thread(target=_bulk_uploader, daemon=True, name="gcs-bulk-upload").start()

    try:
        signal.signal(signal.SIGTERM, _shutdown_handler)
        signal.signal(signal.SIGINT, _shutdown_handler)
    except ValueError:
        # 메인 스레드가 아니면 시그널 등록 불가 (gunicorn worker 등)
        logger.info("[gcs_sync] signal handler skipped (not main thread)")

    logger.info(
        "[gcs_sync] initialized — critical=%ds, bulk_watch=%ds, batch=%ds, stability=%ds",
        CRITICAL_POLL_INTERVAL, BULK_POLL_INTERVAL, BULK_BATCH_INTERVAL, BULK_STABILITY_THRESHOLD,
    )
