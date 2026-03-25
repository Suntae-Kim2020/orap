PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE survey_response (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 기본 정보
    role TEXT,
    role_other TEXT,
    experience TEXT,
    purpose TEXT,
    purpose_other TEXT,
    -- 유용성 (A)
    a1_efficiency INTEGER,
    a2_decision INTEGER,
    a3_strategy INTEGER,
    a4_context INTEGER,
    -- 사용성 (B)
    b1_easy_understand INTEGER,
    b2_intuitive INTEGER,
    b3_find_info INTEGER,
    b4_flow INTEGER,
    b5_help INTEGER,
    -- 정보 품질 (C)
    c1_trust INTEGER,
    c2_relevance INTEGER,
    c3_comprehension INTEGER,
    c4_evidence INTEGER,
    c5_timeliness INTEGER,
    -- 활용 경험 (D)
    d1_actual_use INTEGER,
    d2_changed_decision INTEGER,
    -- 활용 의향 (E)
    e1_continue INTEGER,
    e2_recommend INTEGER,
    -- 서술형 (F)
    f1_strengths TEXT,
    f2_difficulties TEXT,
    f3_trust_improve TEXT,
    f4_feature_request TEXT,
    f5_other TEXT,
    -- 메타
    submitted_at TEXT DEFAULT (datetime('now', 'localtime')),
    ip_address TEXT
, email TEXT);
INSERT INTO survey_response VALUES(1,'faculty','','frequently','analysis','',5,5,5,5,4,4,4,3,2,4,4,3,4,5,4,4,5,5,'우수연구자 랭킹 결과','수식을 이해하는데 어려움이 있음','점수, 순위 산출과정을 이해할 수 있게 설명하는 자료가 필요함',replace('- SCImago Journal Rank(SJR) 기반 성과 분석\n- NI(Nature Index) 기반 성과 분석\n- 교내 연구자 식별','\n',char(10)),'필요한 기능을 지속적으로 보강해주면 좋겠음','2026-02-11 08:59:42','127.0.0.1','kim.suntae@jbnu.ac.kr');
INSERT INTO survey_response VALUES(2,'faculty','','frequently','trend,analysis','',5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,'직관적이라 사용하기 아주 좋습니다.','UI를 개선했으면 합니다. ','','분석하고 싶은 뷰를 요청할 수 있는 메뉴 신설이 필요합니다.','','2026-02-12 01:23:16','61.33.46.194','kimjuseop@jbnu.ac.kr');
INSERT INTO survey_response VALUES(3,'faculty','','frequently','trend,analysis,strategy,report','',5,5,5,5,5,5,5,5,5,5,4,4,5,5,5,5,5,5,'원하는 정보를 잘 분류해주고, 의사 결정 과정의 신속성과 엄밀성을 높일 수 있는 점이 강점으로 판단됨.','','','','','2026-02-12 01:31:03','210.117.164.63','seungbeop.lee@jbnu.ac.kr');
INSERT INTO survey_response VALUES(4,'faculty','','demo_only','other','',3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,'','','','','','2026-02-12 05:04:00','113.198.67.26','lbs.@jbnu.ac.kr');
INSERT INTO survey_response VALUES(5,'staff','','1-2_times','trend,analysis,strategy,report','',5,5,5,5,5,5,5,4,5,5,5,5,5,5,3,3,5,5,'다양한 분석 도구와 표준화된 산출식을 적용하여 정량적·객관적 성과 분석 체계를 구축하였으며, 이에 따라 신뢰성 있는 데이터 기반 연구정책 기획 및 합리적 의사결정 지원이 가능할 것으로 기대됩니다.','연구자 영문명 기반 매칭 작업을 통해 연구자 정보(소속, 직급 등)를 체계적으로 연계할 경우, 연구포상, 연구비 지원, 성과관리 및 정책 의사결정 등에 즉시 활용 가능한 데이터 기반 연구지원 체계 구축이 가능할 것으로 판단됩니다.','','연구지원을 통해 창출된 성과물(논문 등)을 세계대학평가 지표 및 대학 성과지표와 연계하여 기여도를 정량적으로 분석하는 기능을 포함할 경우, 성과 분석 → 정책 기획 → 연구 지원 → 환류로 이어지는 연구지원 전주기 관리 체계를 구현할 수 있으며, 이를 통해 전략적·선순환형 연구지원 체계 고도화가 가능할 것으로 기대됩니다.','','2026-02-12 06:06:25','113.198.67.3','dh7150@jbnu.ac.kr');
INSERT INTO survey_response VALUES(6,'other','회사','demo_only','other','기능 검토',5,5,5,5,5,5,5,5,5,3,3,5,5,5,1,1,3,3,'','','','','','2026-02-12 08:51:18','125.138.72.45','jjpark72@gmail.com');
INSERT INTO survey_response VALUES(7,'faculty','','demo_only','trend,analysis,strategy','',5,5,5,5,5,5,5,5,5,5,5,5,5,5,4,4,5,5,replace('최신 자료를 기반으로, 신뢰성 있는 데이터를 활용한 점\nuser가 쉽게 사용하고 분석 결과를 이해할 수 있는 점\n','\n',char(10)),'불편하거나 어려웠던 점은 없음','분석결과와 지표 관련하여서는 보완이 필요없음','세분화된 카테고리 필요(연구자 직위별, 개인식별 연결 활용)',replace('추후 시스템 업데이트 시에 개인식별코드를 활용하여 개별 연구자들이 교수/대학원/그 외 연구자 등으로 분류될 수 있게 해주세요\n\n학문분야별 (혹은 연구분야별 지표, 예:, QS 지표 등)로도 구분되게 해주세요\n\n','\n',char(10)),'2026-02-13 11:49:06','113.198.67.3','joha0219@jbnu.ac.kr');
COMMIT;
