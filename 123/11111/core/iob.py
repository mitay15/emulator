class IOBData:
    def __init__(self, arr):
        """
        arr — массив объектов IOB из iobDataJson
        Берём первый элемент как "текущий".
        """
        if not arr:
            self.iob = None
            self.activity = None
            self.basaliob = None
            return

        first = arr[0]
        self.iob = first.get("iob")
        self.activity = first.get("activity")
        self.basaliob = first.get("basaliob")

    def __repr__(self):
        return f"IOBData(iob={self.iob}, activity={self.activity})"
