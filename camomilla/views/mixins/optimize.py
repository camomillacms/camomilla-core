class OptimViewMixin:
    def get_serializer_class(self):
        if hasattr(self, "action_serializers"):
            if self.action in self.action_serializers:
                return self.action_serializers[self.action]
        return super().get_serializer_class()

    def get_serializer_context(self):
        return {"request": self.request, "action": self.action}

    def get_queryset(self):
        queryset = super().get_queryset()
        serializer = self.get_serializer_class()
        if hasattr(serializer, "optimize_qs"):
            queryset = serializer.optimize_qs(
                queryset, context=self.get_serializer_context()
            )
        return queryset
