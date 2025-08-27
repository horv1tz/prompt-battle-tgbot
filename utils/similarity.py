from sentence_transformers import SentenceTransformer, util

# Загрузка модели один раз при старте
model = SentenceTransformer('stsb-roberta-large')

def get_similarity_score(sentence1, sentence2):
    """
    Вычисляет балл семантического сходства между двумя фразами.
    Возвращает целое число от 0 до 100.
    """
    # Преобразование фраз в эмбеддинги
    embedding1 = model.encode(sentence1, convert_to_tensor=True)
    embedding2 = model.encode(sentence2, convert_to_tensor=True)

    # Вычисление косинусного сходства
    cosine_score = util.pytorch_cos_sim(embedding1, embedding2)[0][0]

    # Приводим результат к диапазону [0, 100], где 0 - нет сходства.
    # Округляем до целого, чтобы избежать проблем с точностью float
    score = round(max(0, cosine_score.item()) * 100)
    return int(score)
