"""Core loader/inference wrapper around Qwen3 chat models."""

from transformers import AutoModelForCausalLM, AutoTokenizer


class QwenChatModel:
    def __init__(self, model_path: str = "Qwen/Qwen3-1.7B"):
        self.model_path = model_path
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
        )

    def build_input(self, prompt: str, enable_thinking: bool = True):
        """Build the input tensor from a raw prompt string."""
        messages = [{"role": "user", "content": prompt}]
        input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
        return self.tokenizer([input_text], return_tensors="pt").to(self.model.device)

    def generate_response(self, prompt: str, max_new_tokens: int = 32768):
        """Generate a response, splitting out the 'thinking' segment from the final answer."""
        model_inputs = self.build_input(prompt)
        generated_ids = self.model.generate(
            **model_inputs, max_new_tokens=max_new_tokens
        )

        output_ids = generated_ids[0][len(model_inputs.input_ids[0]) :].tolist()

        # Find the end-of-thinking token
        try:
            think_end_token_id = 151668
            index = len(output_ids) - output_ids[::-1].index(think_end_token_id)
        except ValueError:
            index = 0

        thinking = self.tokenizer.decode(
            output_ids[:index], skip_special_tokens=True
        ).strip()
        response = self.tokenizer.decode(
            output_ids[index:], skip_special_tokens=True
        ).strip()

        return thinking, response
