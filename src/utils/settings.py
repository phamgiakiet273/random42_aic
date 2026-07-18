"""Single source of truth for runtime configuration, loaded from .env.

Replaces the legacy configs/*.py classes (one per service, each re-reading
os.getenv on every instantiation). Fields are grouped by service; each
service module should only import the fields it needs from `get_settings()`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Basic ---
    transformers_cache: str = Field("data/weights", alias="TRANSFORMERS_CACHE")
    cuda_device_order: str = Field("PCI_BUS_ID", alias="CUDA_DEVICE_ORDER")
    request_timeout: int = Field(30, alias="REQUEST_TIMEOUT")
    timeout_keep_alive: int = Field(30, alias="TIMEOUT_KEEP_ALIVE")
    huggingface_hub_token: str | None = Field(None, alias="HUGGINGFACE_HUB_TOKEN")

    # --- Dataset / metadata paths ---
    base_path: str = Field("data", alias="BASE_PATH")
    dataset_path_origin: str = Field("data/original", alias="DATASET_PATH_ORIGIN")
    dataset_path_team: str = Field("data", alias="DATASET_PATH_TEAM")
    keyframe_folder_path: str = Field("data", alias="KEYFRAME_FOLDER_PATH")
    split_name: str = Field("low_res_autoshot", alias="SPLIT_NAME")
    split_name_low_res: str = Field("low_res_autoshot", alias="SPLIT_NAME_LOW_RES")
    lowres_format: str = Field(".avif", alias="LOWRES_FORMAT")
    dataset_index: str = Field("data/index", alias="DATASET_INDEX")
    s2t_path: list[str] = Field(default_factory=list, alias="S2T_PATH")
    object_path: str | None = Field(None, alias="OBJECT_PATH")
    fps_path: list[str] = Field(default_factory=list, alias="FPS_PATH")
    shot_path: list[str] = Field(default_factory=list, alias="SHOT_PATH")

    # --- Hub gateway ---
    hub_host: str = Field("0.0.0.0", alias="HUB_HOST")
    hub_port: int = Field(9021, alias="HUB_PORT")
    hub_max_workers: int = Field(5, alias="HUB_MAX_WORKERS")
    base_url: str = Field("http://localhost:9021/", alias="BASE_URL")

    # --- Result manager ---
    result_manager_host: str = Field("0.0.0.0", alias="RESULT_MANAGER_HOST")
    result_manager_port: int = Field(9022, alias="RESULT_MANAGER_PORT")
    result_manager_max_workers: int = Field(5, alias="RESULT_MANAGER_MAX_WORKERS")

    # --- Nginx media server ---
    nginx_image_host: str = Field("http://localhost:9027/img", alias="NGINX_IMAGE_HOST")
    nginx_video_host: str = Field(
        "http://localhost:9027/video", alias="NGINX_VIDEO_HOST"
    )
    nginx_image_port: int = Field(9027, alias="NGINX_IMAGE_PORT")
    nginx_video_port: int = Field(9027, alias="NGINX_VIDEO_PORT")

    # --- SIGLIP v2 (alpha) ---
    siglip_v2_host: str = Field("0.0.0.0", alias="SIGLIP_V2_HOST")
    siglip_v2_port: int = Field(9029, alias="SIGLIP_V2_PORT")
    siglip_v2_host_public: str = Field(
        "http://localhost:9029", alias="SIGLIP_V2_HOST_PUBLIC"
    )
    siglip_v2_max_workers: int = Field(1, alias="SIGLIP_V2_MAX_WORKERS")
    siglip_v2_cuda_visible_devices: str = Field(
        "0", alias="SIGLIP_V2_CUDA_VISIBLE_DEVICES"
    )
    siglip_v2_qdrant_url: str = Field("http://localhost", alias="SIGLIP_V2_QDRANT_URL")
    siglip_v2_qdrant_port: int = Field(6333, alias="SIGLIP_V2_QDRANT_PORT")
    siglip_v2_qdrant_grpc_port: int = Field(6334, alias="SIGLIP_V2_QDRANT_GRPC_PORT")
    siglip_v2_database_name: str = Field("SIGLIP_V2", alias="SIGLIP_V2_DATABASE_NAME")
    siglip_v2_features_path: list[str] = Field(
        default_factory=list, alias="SIGLIP_V2_FEATURES_PATH"
    )
    siglip_v2_features_size: int = Field(1536, alias="SIGLIP_V2_FEATURES_SIZE")
    siglip_v2_dummy_vector_path: str = Field(
        "data/example/cat_siglip2.npy", alias="SIGLIP_V2_DUMMY_VECTOR_PATH"
    )

    # --- SIGLIP v2 (beta) — second model instance for A/B comparison ---
    siglip_v2_b_host: str = Field("0.0.0.0", alias="SIGLIP_V2_B_HOST")
    siglip_v2_b_port: int = Field(9030, alias="SIGLIP_V2_B_PORT")
    siglip_v2_b_host_public: str = Field(
        "http://localhost:9030", alias="SIGLIP_V2_B_HOST_PUBLIC"
    )
    siglip_v2_b_max_workers: int = Field(1, alias="SIGLIP_V2_B_MAX_WORKERS")
    siglip_v2_b_cuda_visible_devices: str = Field(
        "0", alias="SIGLIP_V2_B_CUDA_VISIBLE_DEVICES"
    )
    siglip_v2_b_qdrant_url: str = Field(
        "http://localhost", alias="SIGLIP_V2_B_QDRANT_URL"
    )
    siglip_v2_b_qdrant_port: int = Field(7333, alias="SIGLIP_V2_B_QDRANT_PORT")
    siglip_v2_b_qdrant_grpc_port: int = Field(
        7334, alias="SIGLIP_V2_B_QDRANT_GRPC_PORT"
    )
    siglip_v2_b_database_name: str = Field(
        "SIGLIP_V2_BETA", alias="SIGLIP_V2_B_DATABASE_NAME"
    )
    siglip_v2_b_features_path: list[str] = Field(
        default_factory=list, alias="SIGLIP_V2_B_FEATURES_PATH"
    )
    siglip_v2_b_features_size: int = Field(1536, alias="SIGLIP_V2_B_FEATURES_SIZE")
    siglip_v2_b_dummy_vector_path: str = Field(
        "data/example/cat_siglip2.npy", alias="SIGLIP_V2_B_DUMMY_VECTOR_PATH"
    )

    # --- METACLIP — third model variant, disabled unless its .env vars are set ---
    metaclip_host: str = Field("0.0.0.0", alias="METACLIP_HOST")
    metaclip_port: int = Field(9031, alias="METACLIP_PORT")
    metaclip_host_public: str = Field(
        "http://localhost:9031", alias="METACLIP_HOST_PUBLIC"
    )
    metaclip_max_workers: int = Field(1, alias="METACLIP_MAX_WORKERS")
    metaclip_cuda_visible_devices: str = Field(
        "0", alias="METACLIP_CUDA_VISIBLE_DEVICES"
    )
    metaclip_qdrant_url: str = Field("http://localhost", alias="METACLIP_QDRANT_URL")
    metaclip_qdrant_port: int = Field(8333, alias="METACLIP_QDRANT_PORT")
    metaclip_qdrant_grpc_port: int = Field(8334, alias="METACLIP_QDRANT_GRPC_PORT")
    metaclip_database_name: str = Field("METACLIP", alias="METACLIP_DATABASE_NAME")
    metaclip_features_path: list[str] = Field(
        default_factory=list, alias="METACLIP_FEATURES_PATH"
    )
    metaclip_features_size: int = Field(1024, alias="METACLIP_FEATURES_SIZE")
    metaclip_dummy_vector_path: str = Field(
        "data/example/cat_metaclip.npy", alias="METACLIP_DUMMY_VECTOR_PATH"
    )

    # --- Rerank (dominant-color re-sort) ---
    rerank_host: str = Field("0.0.0.0", alias="RERANK_HOST")
    rerank_port: int = Field(9126, alias="RERANK_PORT")
    rerank_host_public: str = Field("http://localhost:9126", alias="RERANK_HOST_PUBLIC")
    rerank_max_workers: int = Field(1, alias="RERANK_MAX_WORKERS")
    rerank_color_path: list[str] = Field(
        default_factory=list, alias="RERANK_COLOR_PATH"
    )

    # --- Util (translate / neighboring frames / vector lookup) ---
    util_host: str = Field("0.0.0.0", alias="UTIL_HOST")
    util_port: int = Field(9025, alias="UTIL_PORT")
    util_host_public: str = Field("http://localhost:9025", alias="UTIL_HOST_PUBLIC")
    util_max_workers: int = Field(5, alias="UTIL_MAX_WORKERS")
    gg_translate_api_key: str | None = Field(None, alias="GG_TRANSLATE_API_KEY")
    gg_translate_endpoint: str = Field(
        "https://translation.googleapis.com/language/translate/v2",
        alias="GG_TRANSLATE_ENDPOINT",
    )

    # --- DRES submission ---
    submission_host: str = Field("0.0.0.0", alias="SUBMISSION_HOST")
    submission_port: int = Field(9024, alias="SUBMISSION_PORT")
    submission_host_public: str = Field(
        "http://localhost:9024", alias="SUBMISSION_HOST_PUBLIC"
    )
    submission_max_workers: int = Field(5, alias="SUBMISSION_MAX_WORKERS")
    submit_base_url: str = Field(
        "https://eventretrieval.oj.io.vn", alias="SUBMIT_BASE_URL"
    )
    submit_username: str | None = Field(None, alias="SUBMIT_USERNAME")
    submit_password: str | None = Field(None, alias="SUBMIT_PASSWORD")

    # --- VLM extractor (pre-processing pipeline) ---
    prompt_title_extractor_path: str = Field(
        "src/pre_processing/vlm_extractor/prompt/title.txt",
        alias="PROMPT_TITLE_EXTRACTOR_PATH",
    )
    prompt_caption_path: str = Field(
        "src/pre_processing/vlm_extractor/prompt/caption.txt",
        alias="PROMPT_CAPTION_PATH",
    )
    summuray_prompt_path: str = Field(
        "src/pre_processing/vlm_extractor/prompt/summuray.txt",
        alias="SUMMURAY_PROMPT_PATH",
    )
    ocr_prompt_path: str = Field(
        "src/pre_processing/vlm_extractor/prompt/ocr.txt", alias="OCR_PROMPT_PATH"
    )
    model_qwen25_weight_folder: str | None = Field(
        None, alias="MODEL_QWEN25_WEIGHT_FOLDER"
    )
    model_qwen3_weight_folder: str | None = Field(
        None, alias="MODEL_QWEN3_WEIGHT_FOLDER"
    )
    qwen25_cuda_visible_devices: str = Field("0", alias="QWEN25_CUDA_VISIBLE_DEVICES")
    qwen3_cuda_visible_devices: str = Field("0", alias="QWEN3_CUDA_VISIBLE_DEVICES")
    base_output_craw_path: str = Field(
        "data/output_crawl", alias="BASE_OUTPUT_CRAW_PATH"
    )
    max_new_tokens_caption: int = Field(16384, alias="MAX_NEW_TOKENS_CAPTION")

    # --- Logging ---
    log_dir: str = Field("logs/", alias="LOG_DIR")
    log_max_bytes: int = Field(10_485_760, alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(10, alias="LOG_BACKUP_COUNT")
    log_serialize_json: bool = Field(True, alias="LOG_SERIALIZE_JSON")
    log_backtrace: bool = Field(False, alias="LOG_BACKTRACE")
    log_diagnose: bool = Field(False, alias="LOG_DIAGNOSE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
