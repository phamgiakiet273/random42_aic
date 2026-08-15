# API reference

This document describes the API implemented by the current services.  The
recommended public entry point is the **hub** service.  It accepts browser
friendly `multipart/form-data` requests and forwards them to the retrieval,
utility, reranking, and submission services.

For the temporary LAN deployment, replace `<host>` below with the machine's
IP address (currently `172.24.255.75`).  For example, the hub base URL is
`http://172.24.255.75:9021/hub`.

## Conventions

All API responses use this envelope:

```json
{
  "status": 200,
  "message": "Success",
  "data": {}
}
```

`data` is the endpoint-specific payload and may be `null`.  Request validation
errors are returned as HTTP `400` in the same envelope.  Requests over 50 MiB
are rejected with HTTP `413`.

Every service provides:

| Endpoint | Meaning |
| --- | --- |
| `GET /health-check` | Process health check. |
| `GET /docs` | Interactive OpenAPI/Swagger documentation. |
| `GET /redoc` | Alternative OpenAPI documentation. |

The examples below use `curl`.  JSON endpoints require
`Content-Type: application/json`; hub endpoints use `-F` and are sent as form
data.

## Service addresses

| Service | Base path | Port | Intended caller |
| --- | --- | ---: | --- |
| Hub | `/hub` | 9021 | UI and external clients |
| Result manager | `/result_manager` | 9022 | Hub/UI file helpers |
| Submission | `/submission` | 9024 | Hub or trusted admin client |
| Utility | `/util` | 9025 | Hub or trusted client |
| SigLIP Alpha | `/siglip_alpha` | 9029 | Hub/internal retrieval client |
| SigLIP Beta | `/siglip_beta` | 9030 | Hub/internal retrieval client |
| MetaCLIP | `/metaclip` | 9031 | Hub/internal retrieval client |
| Rerank | `/rerank` | 9126 | Hub/internal retrieval client |
| Media (nginx) | `/img`, `/video` | 9027 | Browser media requests |

The direct retrieval, submission, utility, and reranking services are not
authenticated.  They should remain private when this is exposed beyond the
current machine/LAN.

## Common retrieval result

Search endpoints return `data` as an array of ranked frame records.  The exact
set depends on the collection payload, but a record has this shape:

```json
{
  "key": "0_000123",
  "idx_folder": "0",
  "video_name": "video_001",
  "keyframe_id": "000123",
  "fps": 25.0,
  "score": 0.8732,
  "s2t": ["transcript segment"],
  "object": [{"object": "car", "conf": 0.94, "bbox": [10, 20, 100, 80]}],
  "index": 123,
  "video_path": "http://<host>:9027/video/video_001.mp4",
  "frame_path": "http://<host>:9027/img/.../000123.jpg"
}
```

`s2t`, `object`, and the generated media paths can be absent when not requested
or unavailable in the dataset.

## Hub API (recommended client API)

Base URL: `http://<host>:9021/hub`.

### Retrieval

All retrieval endpoints are `POST` form-data requests.  Their successful
response is the common response envelope with a list of ranked frame records
in `data`.

Shared optional form fields:

| Field | Type / default | Meaning |
| --- | --- | --- |
| `k` | integer, `100` | Maximum results. |
| `video_filter` | string or omitted | Limit to a video or video filter expression. |
| `s2t_filter` | string or omitted | Limit by speech-to-text content. |
| `time_in`, `time_out` | string or omitted | Time-range filter. |
| `return_s2t` | boolean, `true` | Include transcript payload. |
| `return_object` | boolean, `true` | Include object-detection payload. |
| `frame_class_filter` | JSON string, `[]` | Frame-class IDs, for example `[1, 4]`. |
| `skip_frames` | JSON string, `[]` | Frames/ranges to omit. |
| `sort_to_news` | boolean, `true` | Apply the service's news-oriented result ordering. |

| Endpoint | Required fields | Additional fields | Purpose |
| --- | --- | --- | --- |
| `POST /siglip_alpha_text_search` | `text` | shared fields | Text-to-frame search using SigLIP Alpha. |
| `POST /siglip_beta_text_search` | `text` | shared fields | Text-to-frame search using SigLIP Beta. |
| `POST /metaclip_text_search` | `text` | shared fields | Text-to-frame search using MetaCLIP. |
| `POST /siglip_alpha_image_search` | `image_path` | shared fields | Search by a readable image path. |
| `POST /siglip_beta_image_search` | `image_path` | shared fields | Search by a readable image path. |
| `POST /metaclip_image_search` | `image_path` | shared fields | Search by a readable image path. |
| `POST /siglip_alpha_temporal_search` | `text` | shared fields, `main_event_index` | Text search with temporal-event handling. |
| `POST /siglip_beta_temporal_search` | `text` | shared fields, `main_event_index` | Same, using SigLIP Beta. |
| `POST /metaclip_temporal_search` | `text` | shared fields, `main_event_index` | Same, using MetaCLIP. |
| `POST /siglip_alpha_scroll` | `video_filter` | `k`, time/filter/return fields, `utility_feature` | Browse frames from a selected video/filter. |
| `POST /siglip_beta_scroll` | `video_filter` | same | Browse using SigLIP Beta collection. |
| `POST /metaclip_scroll` | `video_filter` | same | Browse using MetaCLIP collection. |

`main_event_index` is an integer with default `0`.  `utility_feature` defaults
to `shot` for scroll.  `image_path` is a server-readable path, not base64 image
content; it must be accessible to the hub container.

Example text search:

```bash
curl -X POST http://<host>:9021/hub/siglip_alpha_text_search \
  -F 'text=a red car driving on a city street' \
  -F 'k=10' \
  -F 'return_s2t=true' \
  -F 'frame_class_filter=[]'
```

Example response:

```json
{
  "status": 200,
  "message": "Success",
  "data": [
    {
      "video_name": "video_001",
      "keyframe_id": "000123",
      "score": 0.8732,
      "frame_path": "http://<host>:9027/img/.../000123.jpg"
    }
  ]
}
```

### Utility and result operations

| Endpoint | Required form fields | Optional fields | `data` on success |
| --- | --- | --- | --- |
| `POST /translate` | `text` | `source` (default empty), `target` (default `en`) | Translated text/result from utility service. |
| `POST /rerank_color` | `video_metadata_list` | — | Reordered frame-record list. |
| `POST /get_neighboring_frames` | `frame_num`, `video_name` | `k` (default `1`) | Adjacent frame records. |
| `POST /get_vector_of_frame` | `video_name`, `frame_name` | — | Frame embedding/vector. |
| `POST /get_video_names_of_batch` | `batch_id` as JSON string | — | Video names for batch IDs. |
| `GET /get_session_and_eval_id` | — | — | Current DRES session/evaluation IDs. |
| `GET /update_session_eval_id` | — | — | Refreshes and returns DRES IDs. |

`video_metadata_list` is a JSON-encoded array of common retrieval result
records.  `batch_id` is a JSON-encoded array, such as `[0,1]`.

Example translation:

```bash
curl -X POST http://<host>:9021/hub/translate \
  -F 'text=bonjour le monde' -F 'source=fr' -F 'target=en'
```

Example response:

```json
{"status": 200, "message": "Success", "data": "hello world"}
```

### Submission

These endpoints forward a submission to the configured DRES/evaluation system.
They require a valid configured session and evaluation; do not call them as a
connectivity test.

| Endpoint | Required form fields |
| --- | --- |
| `POST /submit_KIS` | `mediaItemName`, `start` (integer), `end` (integer) |
| `POST /submit_QA` | `answer`, `video_id`, `time` |
| `POST /submit_TRAKE` | `video_id`, `frame_ids` |

All three also accept `session_id` and `eval_id` (both default to the configured
values).  Their `data` is the response returned by the evaluation service.

### Hub media helpers

| Endpoint | Parameters | Behavior |
| --- | --- | --- |
| `GET /ping` | — | Returns a simple hub liveness message. |
| `GET /send_file/{file_path}` | path parameter | Streams a readable server file. |
| `GET /send_img/{full_path}` | path parameter | Redirects to the low-resolution image URL. |
| `GET /send_img_original/{full_path}` | path parameter | Redirects to the original image URL. |
| `GET /send_video/{full_path}` | path parameter | Redirects to the video URL. |

The file and redirect helpers accept paths and must be treated as trusted/admin
endpoints until access controls are added.

## Direct retrieval APIs

Each retrieval service has the same API.  Substitute one of these bases:

```text
http://<host>:9029/siglip_alpha
http://<host>:9030/siglip_beta
http://<host>:9031/metaclip
```

| Endpoint | Request | Response `data` |
| --- | --- | --- |
| `GET /ping` | — | Liveness/model service information. |
| `GET /setup_database` | Query parameters below | Database initialization result. |
| `POST /scroll` | `QdrantRequest` JSON | Ranked/browsed frame records. |
| `POST /text_search` | `RetrievalRequest` JSON with `text` | Ranked frame records. |
| `POST /image_search` | `RetrievalRequest` JSON with base64 `image_data` | Ranked frame records. |
| `POST /temporal_search` | `RetrievalRequest` JSON with `text` | Ranked frame records. |

`POST /scroll` request body:

```json
{
  "k": 10,
  "video_filter": null,
  "s2t_filter": null,
  "time_in": null,
  "time_out": null,
  "return_s2t": true,
  "return_object": true,
  "frame_class_filter": null,
  "skip_frames": [],
  "utility_feature": "shot"
}
```

`POST /text_search`, `/image_search`, and `/temporal_search` use this request
body; provide either `text` or `image_data` according to the endpoint:

```json
{
  "text": "a red car driving on a city street",
  "k": 10,
  "video_filter": null,
  "s2t_filter": null,
  "time_in": null,
  "time_out": null,
  "return_s2t": true,
  "return_object": true,
  "frame_class_filter": null,
  "skip_frames": [],
  "sort_to_news": true,
  "main_event_index": 0
}
```

`image_data` is base64-encoded image data.  `main_event_index` is used by the
temporal endpoint.  `feat` is present in the schema for compatibility but is
not consumed by the current scroll route.

Example direct text query:

```bash
curl -X POST http://<host>:9029/siglip_alpha/text_search \
  -H 'Content-Type: application/json' \
  -d '{"text":"a red car driving on a city street","k":10}'
```

### Database initialization (administrative)

`GET /setup_database` has these query parameters:

| Parameter | Required / default | Meaning |
| --- | --- | --- |
| `unique_json_path` | required | Dataset-relative unique-frame metadata path. |
| `collection_name` | service default | Qdrant collection name. |
| `feature_size` | service default | Embedding dimensionality. |
| `dummy_vector_path` | service default | Dataset-relative vector used to establish dimensions. |
| `create_collection` | `true` | Creates/recreates the collection before indexing. |

This endpoint can erase and rebuild the selected Qdrant collection when
`create_collection=true`.  It is a long-running, administrative operation and
must not be exposed publicly.

Example used for the current Alpha dataset:

```bash
curl --fail --show-error -G http://<host>:9029/siglip_alpha/setup_database \
  --data-urlencode 'unique_json_path=data/utils/check_unique.json'
```

## Utility API (direct)

Base URL: `http://<host>:9025/util`.

| Endpoint | JSON request | Response `data` |
| --- | --- | --- |
| `GET /ping` | — | Liveness information. |
| `POST /translate` | `text` required; `target` default `en`; `source` nullable | Translation result. |
| `POST /get_neighboring_frames` | `frame_num`, `video_name`; `k` default `1` | Neighboring frames. |
| `POST /get_vector` | `video_name`, `frame_name` | Frame vector. |
| `POST /get_video_names` | `batch_id: [int]` | Video names. |

Example:

```bash
curl -X POST http://<host>:9025/util/get_neighboring_frames \
  -H 'Content-Type: application/json' \
  -d '{"frame_num":"000123","video_name":"video_001","k":2}'
```

## Reranking API (direct)

Base URL: `http://<host>:9126/rerank`.

| Endpoint | Request | Response `data` |
| --- | --- | --- |
| `GET /ping` | — | Liveness information. |
| `POST /rerank_color` | JSON array of frame records | Same records reordered by color similarity. |

Each submitted record must contain `key`, `idx_folder`, `video_name`,
`keyframe_id`, `fps`, `score`, `s2t`, `object`, `index`, `video_path`, and
`frame_path`.  The direct reranker is only usable when its supporting rerank
data is deployed.

## Submission API (direct)

Base URL: `http://<host>:9024/submission`.

| Endpoint | Request | Response `data` |
| --- | --- | --- |
| `GET /ping` | — | Liveness information. |
| `GET /relogin` | — | Refreshes login/session state. |
| `GET /get_session_id` | — | Current session ID. |
| `GET /get_eval_id?session_id=...` | `session_id` query | Evaluation ID for the session. |
| `POST /submit_kis` | JSON: `session_id`, `eval_id`, `mediaItemName`, `start`, `end` | Evaluation server response. |
| `POST /submit_qa` | JSON: `session_id`, `eval_id`, `answer`, `video_id`, `time` | Evaluation server response. |
| `POST /submit_trake` | JSON: `session_id`, `eval_id`, `video_id`, `frame_ids` | Evaluation server response. |

Example KIS payload:

```json
{
  "session_id": "session-id",
  "eval_id": "evaluation-id",
  "mediaItemName": "video_001",
  "start": 12,
  "end": 18
}
```

## Result manager API (direct)

Base URL: `http://<host>:9022/result_manager`.

| Endpoint | Parameters | Behavior |
| --- | --- | --- |
| `GET /ping` | — | Liveness information. |
| `GET /send_file/{file_path}` | path parameter | Streams a readable file. |
| `GET /send_img/{video_name}/{frame_name}` | path parameters | Redirects to low-resolution image media. |
| `GET /send_img_original/{video_name}/{frame_name}` | path parameters | Redirects to original image media. |
| `GET /send_video/{video_name}` | path parameter | Redirects to video media. |
| `GET /get_fps/{video_name}` | path parameter | Returns video frames-per-second metadata. |

## Media server

The nginx media server on port 9027 serves paths generated by search results:

| URL prefix | Dataset mapping |
| --- | --- |
| `http://<host>:9027/img/...` | Dataset image files. |
| `http://<host>:9027/video/<name>` | Dataset `original/` video files. |

It supports browser CORS headers, caching for images, and HTTP range requests
for video playback.
