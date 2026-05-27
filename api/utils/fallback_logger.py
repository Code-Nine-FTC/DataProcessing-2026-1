import logging
from datetime import datetime
from typing import Dict, Any

class FallbackLogger:
    def __init__(self):
        self.logger = logging.getLogger("fallback_logger")
    
    def log_fallback_event(self, 
                          tipo_fallback: str,
                          pergunta_original: str,
                          resposta_fallback: str,
                          sugestoes_providas: list,
                          tempo_resposta: float,
                          chat_id: str = None):
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "tipo_fallback": tipo_fallback,
            "pergunta_original": pergunta_original,
            "resposta_fallback": resposta_fallback,
            "sugestoes_providas": sugestoes_providas,
            "tempo_resposta": tempo_resposta,
            "chat_id": chat_id
        }
        
        self.logger.warning(f"Fallback event: {log_data}")
