import asyncio
from sentence_transformers import SentenceTransformer, util

# Загрузка модели один раз при старте
model = SentenceTransformer('stsb-roberta-large')

def _calculate_similarity(sentence1, sentence2):
    """
    Синхронная функция для вычисления сходства.
    """
    embedding1 = model.encode(sentence1, convert_to_tensor=True)
    embedding2 = model.encode(sentence2, convert_to_tensor=True)
    cosine_score = util.pytorch_cos_sim(embedding1, embedding2)[0][0]
    score = round(max(0, cosine_score.item()) * 100)
    return int(score)

async def get_similarity_score(sentence1, sentence2):
    """
    Асинхронно вычисляет балл семантического сходства,
    выполняя ресурсоемкие операции в отдельном потоке.
    Возвращает целое число от 0 до 100.
    """
    return await asyncio.to_thread(_calculate_similarity, sentence1, sentence2)
