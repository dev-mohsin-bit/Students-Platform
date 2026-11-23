import re

TAXONOMY = {
    "Classical ML": {
        "Regression": ["linear regression", "logistic regression", "regression"],
        "Trees & Ensembles": ["decision tree", "random forest", "xgboost", "gradient boosting", "boosting", "bagging", "lightgbm", "catboost"],
        "SVM & KNN": ["svm", "support vector", "knn", "k-nearest", "nearest neighbor"],
        "Clustering & Unsupervised": ["clustering", "k-means", "kmeans", "pca", "dimensionality reduction", "unsupervised"],
        "Model Evaluation": ["cross validation", "cross-validation", "overfitting", "bias variance", "confusion matrix", "roc", "auc", "regularization", "hyperparameter"],
        "Scikit-learn": ["scikit", "sklearn", "scikit-learn"],
    },
    "Deep Learning": {
        "Neural Network Basics": ["neural network", "backprop", "backpropagation", "perceptron", "activation function", "gradient descent"],
        "CNNs": ["cnn", "convolution", "convolutional"],
        "RNNs & LSTMs": ["rnn", "lstm", "gru", "recurrent"],
        "Training & Optimization": ["optimizer", "adam", "batch norm", "dropout", "learning rate", "loss function"],
        "PyTorch & TensorFlow": ["pytorch", "tensorflow", "keras", "jax"],
    },
    "NLP & LLMs": {
        "Transformers & Attention": ["transformer", "attention", "bert", "self-attention"],
        "Large Language Models": ["llm", "gpt", "llama", "language model", "chatgpt", "claude", "gemini", "mistral", "deepseek"],
        "Fine-tuning & Prompting": ["fine-tun*", "finetun*", "lora", "prompt", "rlhf", "instruction tuning"],
        "RAG & Embeddings": ["rag", "retrieval", "embedding", "vector database", "vector db", "langchain", "llamaindex"],
        "Classic NLP": ["nlp", "tokeniz*", "word2vec", "sentiment", "text classification", "named entity"],
    },
    "Computer Vision": {
        "Detection & Segmentation": ["object detection", "yolo", "segmentation", "image classification", "resnet", "vision transformer", "vit", "detr"],
        "Vision Basics": ["computer vision", "opencv", "image recognition", "image processing", "face recognition", "ocr", "pose estimation"],
        "3D & Video Vision": ["nerf", "gaussian splatting", "3d reconstruction", "depth estimation", "video understanding"],
        "Self-Driving & Medical": ["self-driving", "autonomous driving", "autonomous vehicle", "medical imaging", "lidar"],
        "Multimodal & Vision-Language": ["multimodal", "vision language", "vlm", "image captioning"],
    },
    "Generative AI": {
        "Diffusion & Image Generation": ["diffusion", "stable diffusion", "midjourney", "dall-e", "image generation", "text-to-image"],
        "GANs & VAEs": ["gan", "vae", "autoencoder", "generative adversarial"],
        "Video & Audio Generation": ["sora", "video generation", "text-to-video", "text to speech", "voice cloning", "music generation"],
        "AI Agents": ["agent", "agentic", "mcp", "tool use", "autogen", "crewai"],
    },
    "Reinforcement Learning": {
        "RL Fundamentals": ["reinforcement learning", "q-learning", "policy gradient", "markov decision", "reward"],
        "Deep RL & Games": ["alphago", "alphazero", "dqn", "ppo", "deep rl", "atari"],
        "Robotics": ["robot", "robotics", "embodied"],
    },
    "Math & Statistics": {
        "Linear Algebra": ["linear algebra", "matrix", "eigen*", "vector"],
        "Calculus & Optimization": ["calculus", "derivative", "gradient"],
        "Probability & Statistics": ["probability", "statistics", "bayes", "bayesian", "distribution", "hypothesis", "p-value", "central limit"],
    },
    "Data Science & Python": {
        "Python for ML": ["python", "numpy", "pandas", "jupyter", "matplotlib"],
        "Data Prep & Features": ["data cleaning", "feature engineering", "preprocessing", "eda", "data analysis"],
        "SQL & Data Tools": ["sql", "spark", "kaggle"],
    },
    "MLOps & Deployment": {
        "Deployment": ["deploy*", "docker", "kubernetes", "flask", "fastapi", "streamlit"],
        "MLOps": ["mlops", "pipeline", "mlflow", "monitoring", "production"],
        "Hardware & Scaling": ["gpu", "cuda", "distributed training", "quantization", "inference"],
    },
    "Research & Papers": {
        "Paper Explanations": ["paper", "arxiv", "research paper"],
        "Interpretability & Safety": ["interpretab*", "alignment", "ai safety", "mechanistic", "circuits", "explainab*"],
        "Benchmarks & Evals": ["benchmark", "eval*", "leaderboard"],
    },
    "AI News & Careers": {
        "Model Releases": ["release", "launch", "announce*", "gpt-5", "new model"],
        "Industry & Business": ["openai", "nvidia", "anthropic", "microsoft", "startup", "agi"],
        "Interviews & Talks": ["interview", "podcast", "keynote", "conversation"],
        "Careers & Learning": ["roadmap", "career", "how to learn", "beginner", "course", "bootcamp"],
    },
}

def _pattern(kw):
    if kw.endswith("*"):                      # prefix match, e.g. "fine-tun*"
        return r"\b" + re.escape(kw[:-1])
    return r"\b" + re.escape(kw) + r"s?\b"    # whole word, plural allowed

COMPILED = {
    (topic, sub): re.compile("|".join(_pattern(k) for k in kws), re.IGNORECASE)
    for topic, subs in TAXONOMY.items()
    for sub, kws in subs.items()
}

def tag_title(title):
    return [key for key, rx in COMPILED.items() if rx.search(title)]