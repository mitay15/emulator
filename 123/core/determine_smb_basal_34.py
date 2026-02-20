# emulator/core/determine_smb_basal_34.py

class DetermineSMBBasal34:
    """
    Полный перенос алгоритма determineSMB-basal.js из AAPS 3.4.
    """

    def __init__(self):
        pass

    def compute(self, ci):
        """
        Основная точка входа.
        ci — CycleInput
        Возвращает SuggestedData
        """

        # Распаковка входных данных
        g, profile, autoisf, iob = ci.to_core()

        # Здесь будет логика:
        # 1. Определение deviation
        # 2. Определение BGI
        # 3. Определение autosens
        # 4. Определение UAM
        # 5. Определение IOBpredBG
        # 6. Определение ZTpredBG
        # 7. Определение UAMpredBG
        # 8. Определение insulinReq
        # 9. Ограничения maxIOB / maxSMB
        # 10. Ограничения по безопасности
        # 11. Формирование SuggestedData

        raise NotImplementedError("Алгоритм ещё переносится")
