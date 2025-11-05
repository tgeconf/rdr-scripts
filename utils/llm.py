from typing import List
import os
import numpy as np
from openai import OpenAI
from volcenginesdkarkruntime import Ark

def _call_embedding_api(batch_texts: List[str]) -> List[List[float]]:
    """
    调用第三方Embedding服务，获取一批文本的Embedding向量。
    使用OpenAI客户端格式，参考test.py的实现
    """
    # Get environment variables
    api_key = os.environ.get("VOLC_LLM_KEY") or os.environ.get("ARK_API_KEY", "")
    base_url = os.environ.get("EMBEDDING_BASE_URL", "")
    model = os.environ.get("EMBEDDING_MODEL", "")

    print(f"Debug - API Key: {api_key[:10]}..." if api_key else "Debug - No API key")
    print(f"Debug - Base URL: {base_url}")
    print(f"Debug - Model: {model}")

    if not api_key or not base_url or not model:
        print(
            "环境变量未配置完整：LLM_KEY/ARK_API_KEY、LLM_BASE_URL或EMBEDDING_MODEL缺失。"
        )
        print("使用随机向量作为fallback")
        return [np.random.normal(0, 1, 1536).tolist() for _ in batch_texts]

    try:
        print(f"----- embeddings request for {len(batch_texts)} texts -----")

        client = Ark(api_key=api_key)

        resp = client.embeddings.create(
            model=model,
            input=batch_texts,
            encoding_format="float",
        )

        print(f"Response received: {type(resp)}")
        print(f"Data items: {len(resp.data)}")

        # 提取embedding向量 - 和test.py保持一致的访问方式
        embeddings = []
        for item in resp.data:
            embeddings.append(item.embedding)

        if len(embeddings) != len(batch_texts):
            print("警告：返回的Embedding数量与输入文本数量不一致。")

        print(
            f"成功获取 {len(embeddings)} 个embedding向量，每个向量维度: {len(embeddings[0])}"
        )
        return embeddings

    except Exception as e:
        print(f"调用第三方Embedding服务异常: {e}")
        print(f"异常类型: {type(e)}")
        import traceback

        traceback.print_exc()
        return []

def call_embedding_model(texts: List[str]) -> np.ndarray:
    """Calculate embeddings for a list of texts using custom embedding API"""
    if not texts:
        return np.array([])

    print(f"Calculating embeddings for {len(texts)} texts...")
    embeddings = _call_embedding_api(texts)

    # Convert to numpy array
    return np.array(embeddings)

import time
import os
from openai import OpenAI
import re

DS_ERROR_CODES = [{
    'code': 400,
    'message': 'Bad Request'  # skip
}, {
    'code': 401,
    'message': 'Unauthorized'  # terminate
}, {
    'code': 402,
    'message': 'Payment Required'  # terminate
}, {
    'code': 422,
    'message': 'Wrong input'  # skip
}, {
    'code': 429,
    'message': 'Rate limit exceeded'  # retry
}, {
    'code': 500,
    'message': 'Internal Server Error'  # retry
}, {
    'code': 503,
    'message': 'Service Unavailable'  # retry
}, {
    'code': 403,
    'message': 'Forbidden'  # terminate
}]

SUCCESS_CODE = 200
BAD_REQUEST_ERROR = 400
UNAUTHORIZED_ERROR = 401
FORBIDDEN_ERROR = 403
MAX_LENGTH_EXCEEDED_ERROR = 406
INTERNAL_SERVER_ERROR = 500  # retry
BAD_GATEWAY_ERROR = 502
SERVICE_UNAVAILABLE_ERROR = 503
GATEWAT_TIMEOUT_ERROR = 504  # retry
SKIP_ERROR = 998
UNKNOWN_ERROR = 999


def extract_error_code(error_message):
    match = re.search(r'Error code: (\d+)', error_message)

    if match:
        error_code = match.group(1)
        return int(error_code)
    else:
        return UNKNOWN_ERROR


class DSChat(object):
    def __init__(self):
        self._key = None
        self._base_url = None
        self._client = None
        self.errors = set()  # error codes

    def init(self, key_info):
        print('Using ds key: ', key_info)
        if key_info:
            self._key = key_info['key']
            self._base_url = key_info['base_url']
            self._client = OpenAI(api_key=self._key,
                                  base_url=self._base_url)
            return True
        else:
            return False

    def print_response(self, response):
        if response and response.choices and response.choices[0].message and response.choices[0].message.content:
            print(f'** DS Response:\n\t{response.choices[0].message.content}')

    def chat(self, model_name: str, prompt: str, chat_hist=[], temp=0.1):
        messages = chat_hist + [
            {'role': 'user', 'content': prompt}
        ]

        max_retries = 5  # Number of retries
        delay = 20  # Seconds to wait between retries

        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    # max_tokens=4096,
                    # frequency_penalty=0.2,
                    temperature=temp,
                    stream=False
                )
                # self.print_response(response)

                return {
                    "content": response.choices[0].message.content,
                    "error_code": 200,
                    "output_token_len": response.usage.completion_tokens
                }
            except Exception as e:
                print(f"Attempt {attempt+1} failed: {e}", type(e))
                error_code = extract_error_code(str(e))
                print(
                    f"Attempt {attempt+1} failed: {e}, error code: {error_code}")
                # 处理不同的错误码
                if error_code != INTERNAL_SERVER_ERROR and error_code != GATEWAT_TIMEOUT_ERROR and error_code != MAX_LENGTH_EXCEEDED_ERROR:
                    print('done chatting with http error', error_code)
                    return {
                        "content": None,
                        "error_code": error_code,
                        "output_token_len": 0
                    }
                time.sleep(delay)
        return {
            "content": None,
            "error_code": 403,
            "output_token_len": 0
        }


# Load environment variables
try:
    from env_loader import load_env_file
    load_env_file()
except ImportError:
    print("Failed to load environment variables")
    # Fallback: try to load from system environment
    pass

# Get API key from environment, with fallback
ds_api_key = os.environ.get("DS_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
ds_base_url = os.environ.get("DS_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL", "")
if not ds_api_key:
    print("Warning: No API key found in environment variables (DS_API_KEY or DEEPSEEK_API_KEY)")
    print("Please set up your .env file or export the environment variable")
if not ds_base_url:
    print("Warning: No base URL found in environment variables (DS_BASE_URL or DEEPSEEK_BASE_URL)")
    print("Please set up your .env file or export the environment variable")
ds_chat = DSChat()
ds_chat.init({
    "key": ds_api_key,
    "base_url": ds_base_url,
})


def call_llm_model(model_name: str, prompt: str, temperature: float = 0.1):
    response = ds_chat.chat(model_name, prompt, temp=temperature)
    if response['error_code'] != SUCCESS_CODE:
        if response['error_code'] == MAX_LENGTH_EXCEEDED_ERROR:
            print('TOO LONG, breaking...')
            return None
        print('Error in generating response, breaking...')
        return None

    result = response['content']

    max_continue = 5
    continue_count = 0
    while True:
        if response['output_token_len'] >= 4095:
            chat_hist = [
                {'role': 'user', 'content': prompt},
                {'role': 'assistant', 'content': response['content']}
            ]
            response = ds_chat.chat(
                model_name, 'continue', chat_hist, temperature)
            print('--- current output len: ', response['output_token_len'])
            if response['error_code'] != SUCCESS_CODE:
                if response['error_code'] == MAX_LENGTH_EXCEEDED_ERROR:
                    print('TOO LONG, breaking...')
                    return result
                print('Error in generating response, breaking...')
                return result
            result += response['content']
            print('--- current result: ', result)
            continue_count += 1
            if continue_count >= max_continue:
                # print('--- done generate all')
                break
        else:
            # print('--- done generate all')
            break

    return result


if __name__ == "__main__":
    prompt = "Who are you?"
    # result = call_llm_model('deepseek-reasoner', prompt)
    # print(result)
    embeddings = call_embedding_model([prompt])
    print(embeddings)