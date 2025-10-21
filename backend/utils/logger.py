import json
from datetime import datetime
from pathlib import Path
from typing import Any


class Logger:
    """Handles logging of all simulation events to JSON files."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"{session_id}.json"
        
    def log_event(self, event_type: str, data: Any) -> None:
        """
        Log an event to the session's log file.
        
        Args:
            event_type: Type of event (e.g., 'session_start', 'message', 'llm_call', 'error')
            data: Event data (will be JSON serialized)
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        
        # Append to log file (JSON Lines format - one JSON object per line)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def log_session_start(self, experimental_config: dict, simulation_config: dict) -> None:
        """Log session initialization with config snapshots."""
        self.log_event("session_start", {
            "session_id": self.session_id,
            "experimental_config": experimental_config,
            "simulation_config": simulation_config
        })
    
    def log_session_end(self, reason: str = "completed") -> None:
        """Log session termination."""
        self.log_event("session_end", {
            "session_id": self.session_id,
            "reason": reason
        })
    
    def log_message(self, message: dict) -> None:
        """Log a message (user or agent)."""
        self.log_event("message", message)
    
    def log_llm_call(self, agent_name: str, prompt: str, response: str, error: str = None) -> None:
        """Log an LLM API call."""
        self.log_event("llm_call", {
            "agent_name": agent_name,
            "prompt": prompt,
            "response": response,
            "error": error
        })
    
    def log_error(self, error_type: str, error_message: str, context: dict = None) -> None:
        """Log an error."""
        self.log_event("error", {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        })