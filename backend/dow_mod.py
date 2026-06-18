import os
from fast_alpr import ALPR

# Устанавливаем переменные окружения, если нужно подсказать библиотеке, откуда брать модели
# (иногда помогает, если стандартный путь HuggingFace 'глючит')
# os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

def run_ocr(image_path):
    print("Инициализирую ALPR (если моделей нет, начнется загрузка)...")
    
    try:
        # Инициализация сама дергает загрузку моделей, если их нет в /root/.cache/
        alpr = ALPR()
        
        print("Модели загружены. Распознаю...")
        results = alpr.predict(image_path)
        
        for plate in results:
            print(f"Найдено: {plate.plate_number} (уверенность: {plate.score:.2f})")
            
    except Exception as e:
        print(f"Ошибка при работе ALPR: {e}")
        print("Если ошибка сетевая (Connection Timeout), значит сервер Proxmox не может достучаться до HuggingFace.")

if __name__ == "__main__":
    # Укажи путь к своей картинке
    run_ocr("test.jpg")
