import asyncio
from difflib import SequenceMatcher

def _calculate_similarity(sentence1, sentence2):
    """
    Синхронная функция для вычисления сходства с помощью SequenceMatcher.
    """
    similarity = SequenceMatcher(None, sentence1, sentence2).ratio()
    return int(similarity * 100)

async def get_similarity_score(sentence1, sentence2):
    """
    Асинхронно вычисляет балл семантического сходства,
    выполняя ресурсоемкие операции в отдельном потоке.
    Возвращает целое число от 0 до 100.
    """
    return await asyncio.to_thread(_calculate_similarity, sentence1, sentence2)
