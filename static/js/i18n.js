// 다국어 지원 시스템 (i18n)
const i18n = {
    currentLang: 'ko',
    translations: {},
    ready: false,
    onLanguageChangeCallbacks: [],

    // 초기화
    async init() {
        // 저장된 언어 설정 로드
        const savedLang = localStorage.getItem('orap_language') || 'ko';
        await this.setLanguage(savedLang);
        this.ready = true;
        // 초기화 완료 이벤트 발생
        window.dispatchEvent(new CustomEvent('i18nReady'));
    },

    // 언어 변경 콜백 등록
    onLanguageChange(callback) {
        this.onLanguageChangeCallbacks.push(callback);
    },

    // 언어 설정
    async setLanguage(lang) {
        try {
            // 번역 파일 로드
            const response = await fetch(`/static/lang/${lang}.json`);
            if (!response.ok) throw new Error('Translation file not found');
            this.translations = await response.json();
            this.currentLang = lang;

            // 로컬 스토리지에 저장
            localStorage.setItem('orap_language', lang);

            // 페이지 번역 적용
            this.translatePage();

            // 언어 선택 UI 업데이트
            this.updateLanguageSelector();

            // 언어 변경 콜백 호출
            this.onLanguageChangeCallbacks.forEach(cb => {
                try { cb(lang); } catch(e) { console.error(e); }
            });

        } catch (error) {
            console.error('Failed to load language:', error);
        }
    },

    // 번역 텍스트 가져오기
    t(key) {
        const keys = key.split('.');
        let value = this.translations;
        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                return key; // 번역이 없으면 키 반환
            }
        }
        return value;
    },

    // 페이지 전체 번역 적용
    translatePage() {
        // data-i18n 속성이 있는 모든 요소 번역
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = this.t(key);
            if (translation !== key) {
                el.textContent = translation;
            }
        });

        // data-i18n-placeholder 속성 (입력 필드 placeholder)
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            const translation = this.t(key);
            if (translation !== key) {
                el.placeholder = translation;
            }
        });

        // data-i18n-title 속성 (툴팁)
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            const translation = this.t(key);
            if (translation !== key) {
                el.title = translation;
            }
        });

        // data-i18n-html 속성 (HTML 포함)
        document.querySelectorAll('[data-i18n-html]').forEach(el => {
            const key = el.getAttribute('data-i18n-html');
            const translation = this.t(key);
            if (translation !== key) {
                el.innerHTML = translation;
            }
        });
    },

    // 언어 선택기 업데이트
    updateLanguageSelector() {
        const selector = document.getElementById('language-selector');
        if (selector) {
            selector.value = this.currentLang;
        }

        // 현재 언어 표시 업데이트
        const currentLangDisplay = document.getElementById('current-lang-display');
        if (currentLangDisplay) {
            currentLangDisplay.textContent = this.currentLang === 'ko' ? '한국어' : 'English';
        }
    },

    // 언어 토글
    toggleLanguage() {
        const newLang = this.currentLang === 'ko' ? 'en' : 'ko';
        this.setLanguage(newLang);
    }
};

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    i18n.init();
});

// 전역에서 사용 가능하도록
window.i18n = i18n;
