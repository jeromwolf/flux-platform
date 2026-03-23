import { createI18n } from 'vue-i18n'
import ko from './locales/ko'
import en from './locales/en'

const savedLocale = localStorage.getItem('imsp-language') || 'ko'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'ko',
  messages: { ko, en },
})

export default i18n

export function setLocale(locale: string) {
  i18n.global.locale.value = locale as 'ko' | 'en'
  localStorage.setItem('imsp-language', locale)
}
