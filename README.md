# AAPS Emulator — Full AutoISF Algorithm Emulator

AAPS Emulator — это полностью воспроизводимый Python‑эмулятор алгоритма AutoISF из AndroidAPS.  
Проект создан для:

- точного сравнения расчётов Python ↔ AAPS
- анализа поведения алгоритма на реальных логах
- визуализации predBG, IOB, COB, UAM, ZT
- генерации интерактивных отчётов
- автоматической проверки полного соответствия алгоритму

## 🚀 Возможности

- Полная эмуляция AutoISF (DetermineBasal + AutoISF pipeline)
- Сравнение всех ключевых расчётов:
  - eventualBG, minPredBG, minGuardBG
  - SMB, temp basal, insulinReq
  - autosens, variable_sens
  - predBG curves (IOB/COB/UAM/ZT)
- Генерация интерактивного HTML‑отчёта
- Тепловая карта расхождений
- Полный автоматический валидатор (`validate_all.py`)
- Инструменты для анализа логов AAPS

## 📦 Установка

```bash
pip install -e .
