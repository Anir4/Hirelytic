# summarize_cv.py
import os
import json
from llama_inference import run_llama_fast
import codecs


def summarize_cv(cv_text: str) -> dict:
    prompt = f"""
    CV:
    {cv_text}

    Extract information and return ONLY this JSON structure with no other text:
    {{"Name":"","Email":"","Phone":"","Education":[{{"Degree":"","School":""}}],"Experience":[{{"Company":"","Role":""}}],"Skills":[""],"Languages":[""]}}

    Ignore any date or year fields
    Replace empty strings with actual data. No explanations, no "here is", just JSON:
    """
    
    response = run_llama_fast(prompt, max_tokens=800)
    print(f"Sumary: {response}")
    start_idx = response.find('{')
    end_idx = response.rfind('}') + 1

    if start_idx != -1 and end_idx != -1:
        json_str = response[start_idx:end_idx]
        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse extracted JSON block: {e}")

    # No valid JSON block found, try entire response
    try:
        return {"raw": response}
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse response as JSON: {e}")
    


def process_folder(input_dir="data/texts", output_dir="data/summaries"):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if not filename.endswith(".txt"):
            continue
        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        summary = summarize_cv(text)
        outpath = os.path.join(output_dir, filename.replace(".txt", ".json"))
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"✓ Summarized {filename} → {outpath}")

if __name__ == "__main__":
    process_folder()
