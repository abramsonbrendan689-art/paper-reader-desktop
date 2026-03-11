from __future__ import annotations


class ClassificationService:
    KEYWORD_TOPICS: dict[str, tuple[str, ...]] = {
        "NLP": ("language", "translation", "bert", "gpt", "nlp", "token"),
        "CV": ("image", "vision", "detection", "segmentation", "cnn"),
        "Reinforcement Learning": ("reinforcement", "policy", "agent", "reward"),
        "Data Mining": ("dataset", "clustering", "mining", "retrieval"),
        "Systems": ("distributed", "latency", "throughput", "system"),
    }

    def classify(self, metadata: dict[str, str]) -> str:
        target = " ".join(
            [
                metadata.get("title", ""),
                metadata.get("abstract", ""),
                metadata.get("keywords", ""),
            ]
        ).lower()

        best_topic = "Uncategorized"
        best_score = 0
        for topic, keywords in self.KEYWORD_TOPICS.items():
            score = sum(1 for k in keywords if k in target)
            if score > best_score:
                best_score = score
                best_topic = topic
        return best_topic

