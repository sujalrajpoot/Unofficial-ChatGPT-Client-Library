from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
import requests
import json

class ChatGPTError(Exception):
    """Base exception class for ChatGPT client errors."""
    pass

class APIError(ChatGPTError):
    """Exception raised for API-related errors."""
    def __init__(self, status_code: int, message: str, description: str):
        self.status_code = status_code
        self.message = message
        self.description = description
        super().__init__(f"Status Code: {status_code}, Error: {message}, Description: {description}")

class ModelNotFoundError(ChatGPTError):
    """Exception raised when an invalid model is specified."""
    pass

class TaskStatus(Enum):
    """Enumeration of possible task statuses."""
    PENDING = auto()
    COMPLETED = auto()
    ERROR = auto()
    NOT_FOUND = auto()

@dataclass
class Message:
    """Data class representing a chat message."""
    role: str
    content: str

@dataclass
class TaskResponse:
    """Data class representing a task response."""
    id: str
    status: TaskStatus
    response: Optional[str] = None

class AIModel(ABC):
    """Abstract base class for AI model implementations."""
    
    @abstractmethod
    def generate_response(self, messages: List[Message], **kwargs) -> str:
        """Generate a response from the model."""
        pass

    @abstractmethod
    def validate_model(self, model_name: str) -> bool:
        """Validate if the model name is supported."""
        pass

class GPTClient(AIModel):
    """
    A client for interacting with GPT models through an API.
    
    Attributes:
        base_url (str): The base URL for the API
        available_models (Dict[str, str]): Dictionary of available model mappings
        timeout (int): Request timeout in seconds
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize the GPT client.
        
        Args:
            timeout (int): Request timeout in seconds. Defaults to 30.
        """
        self.base_url = "https://nexra.aryahcr.cc/api/chat"
        self.timeout = timeout
        self.available_models = {
            "GPT-4": "gpt-4",
            "GPT-4-0613": "gpt-4-0613",
            "GPT-4-32k": "gpt-4-32k",
            "GPT-4-0314": "gpt-4-0314",
            "GPT-4-32k-0314": "gpt-4-32k-0314",
            "GPT-3.5-Turbo": "gpt-3.5-turbo",
            "GPT-3.5-Turbo-16k": "gpt-3.5-turbo-16k",
            "GPT-3.5-Turbo-0613": "gpt-3.5-turbo-0613",
            "GPT-3.5-Turbo-16k-0613": "gpt-3.5-turbo-16k-0613",
            "GPT-3.5-Turbo-0301": "gpt-3.5-turbo-0301",
            "Text-Davinci-003": "text-davinci-003",
            "Text-Davinci-002": "text-davinci-002",
            "Code-Davinci-002": "code-davinci-002",
            "GPT-3": "gpt-3",
            "Text-Curie-001": "text-curie-001",
            "Text-Babbage-001": "text-babbage-001",
            "Text-Ada-001": "text-ada-001",
            "Davinci": "davinci",
            "Curie": "curie",
            "Babbage": "babbage",
            "Ada": "ada",
            "Babbage-002": "babbage-002",
            "Davinci-002": "davinci-002",
            "GPT-4o": "gpt-4o",
            "ChatGPT": "chatgpt"
        }

    def validate_model(self, model_name: str) -> bool:
        """
        Validate if the specified model is available.
        
        Args:
            model_name (str): Name of the model to validate
            
        Returns:
            bool: True if model is valid, False otherwise
        """
        return model_name in self.available_models

    def _create_request_payload(self, messages: List[Message], model: str) -> Dict[str, Any]:
        """
        Create the request payload for the API.
        
        Args:
            messages (List[Message]): List of messages to include in the request
            model (str): Name of the model to use
            
        Returns:
            Dict[str, Any]: Formatted request payload
        """
        return {
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "model": model,
            "markdown": False
        }

    def _handle_api_error(self, response: requests.Response) -> None:
        """
        Handle API error responses.
        
        Args:
            response (requests.Response): Response object from the API
            
        Raises:
            APIError: When an API error occurs
        """
        error_mappings = {
            429: "Too Many Requests",
            400: "Bad Request",
            500: "Internal Server Error"
        }
        
        error_message = response.json().get('message', 'Unknown error')
        description = error_mappings.get(response.status_code, "Unexpected Error")
        raise APIError(response.status_code, error_message, description)

    def _poll_task_status(self, task_id: str) -> TaskResponse:
        """
        Poll the task status until completion or error.
        
        Args:
            task_id (str): ID of the task to poll
            
        Returns:
            TaskResponse: Response containing task status and result
        """
        while True:
            response = requests.get(f"{self.base_url}/task/{task_id}")
            
            if response.status_code != 200:
                raise APIError(response.status_code, "Task polling failed", "Failed to retrieve task status")
            
            data = response.json()
            status = data.get("status")
            
            if status == "completed":
                return TaskResponse(task_id, TaskStatus.COMPLETED, data.get('gpt'))
            elif status == "pending":
                continue
            else:
                return TaskResponse(task_id, TaskStatus[status.upper()])

    def generate_response(self, messages: List[Message], model: str = "GPT-4") -> str:
        """
        Generate a response using the specified model.
        
        Args:
            messages (List[Message]): List of messages to process
            model (str): Name of the model to use. Defaults to "GPT-4"
            
        Returns:
            str: Generated response
            
        Raises:
            ModelNotFoundError: If the specified model is invalid
            APIError: If an API error occurs
        """
        if not self.validate_model(model):
            raise ModelNotFoundError(f"Invalid model: {model}. Available models: {', '.join(self.available_models.keys())}")

        headers = {"Content-Type": "application/json"}
        payload = self._create_request_payload(messages, self.available_models[model])

        try:
            response = requests.post(
                f"{self.base_url}/gpt",
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout
            )

            if response.status_code != 200:
                self._handle_api_error(response)

            task_id = response.json().get("id")
            task_response = self._poll_task_status(task_id)

            if task_response.status == TaskStatus.COMPLETED:
                return task_response.response
            else:
                raise ChatGPTError(f"Task failed with status: {task_response.status}")

        except requests.exceptions.RequestException as e:
            raise ChatGPTError(f"Request failed: {str(e)}")

def main():
    """Example usage of the GPT client."""
    client = GPTClient()
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hi")
    ]
    try:
        response = client.generate_response(messages, model="ChatGPT")
        print(f"Response: {response}")
    except ChatGPTError as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()