import os
from typing import Optional
import replicate

class ReplicateVideoProvider:
    def __init__(self, api_token: Optional[str] = None, model: Optional[str] = None):
        self.api_token = api_token or os.getenv("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise RuntimeError("REPLICATE_API_TOKEN is not set")
        self.model = model or os.getenv("REPLICATE_MODEL", "luma/photon")
        self.client = replicate.Client(api_token=self.api_token)

    def generate(self, image_path: str, prompt: str) -> str:
        # Many Replicate models return a URL to the video; we return that as string
        # Example inputs vary by model; for MVP we pass prompt and image.
        with open(image_path, "rb") as f:
            output = self.client.run(
                self.model,
                input={
                    "prompt": prompt,
                    "image": f,
                },
            )
        # Output can be a list/str depending on model. Normalize to string URL.
        if isinstance(output, list) and output:
            return str(output[-1])
        return str(output)
