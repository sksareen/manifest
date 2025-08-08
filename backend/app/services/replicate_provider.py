import os
from typing import Optional, Dict, Any
import replicate

class ReplicateVideoProvider:
    def __init__(self, api_token: Optional[str] = None, model: Optional[str] = None):
        self.api_token = api_token or os.getenv("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise RuntimeError("REPLICATE_API_TOKEN is not set")
        self.model = model or os.getenv("REPLICATE_MODEL", "luma/photon")
        self.client = replicate.Client(api_token=self.api_token)

    def generate(self, image_path: Optional[str], prompt: str, extra_inputs: Optional[Dict[str, Any]] = None) -> str:
        """Run the configured Replicate video model.

        Many Replicate models return a URL to the generated video; normalize to string.
        Some models support additional inputs like duration/num_frames/fps; pass via extra_inputs.
        """
        inputs: Dict[str, Any] = {"prompt": prompt}
        if extra_inputs:
            # Filter out None values to avoid sending invalid keys
            inputs.update({k: v for k, v in extra_inputs.items() if v is not None})

        if image_path:
            with open(image_path, "rb") as f:
                inputs["image"] = f
                output = self.client.run(self.model, input=inputs)
        else:
            output = self.client.run(self.model, input=inputs)

        # Output can be a list/str depending on model. Normalize to string URL.
        if isinstance(output, list) and output:
            return str(output[-1])
        return str(output)
