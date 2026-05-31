class FallbackMetrics:
    def __init__(self):
        self.metrics = {
            "total_fallbacks": 0,
            "por_tipo": {
                "nlp_fallback": 0,
                "data_fallback": 0,
                "connection_fallback": 0,
                "generic_fallback": 0
            },
            "tempo_medio": 0.0
        }
    
    def registrar_fallback(self, tipo_fallback: str, tempo_resposta: float):
        self.metrics["total_fallbacks"] += 1
        if tipo_fallback in self.metrics["por_tipo"]:
            self.metrics["por_tipo"][tipo_fallback] += 1
        
        # Calcular nova média ponderada iterativa
        total = self.metrics["total_fallbacks"]
        if total > 0:
            avg = self.metrics["tempo_medio"]
            self.metrics["tempo_medio"] = avg + (tempo_resposta - avg) / total
