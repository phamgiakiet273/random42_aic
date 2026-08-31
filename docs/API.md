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

Search endpoints return `data` as an array of ranked frame records:

```json
{
  "key": "705529",
  "idx_folder": 1,
  "video_name": "K15_V011.mp4",
  "keyframe_id": "05855",
  "fps": 25.0,
  "score": 0.1272948384284973,
  "frame_class": 2,
  "is_unique": true,
  "related_start_frame": 5003,
  "related_end_frame": 6384,
  "s2t": ["trong", "cai", "quy dinh"],
  "index": 0
}
```

Records are returned in final rank order; `index` is that rank. Clients should
not re-sort (doc comment [o]).

### Changes from the 2025 shape

- **Numbers are numbers.** `idx_folder`, `frame_class` and `related_*` are
  integers, `fps` and `score` floats. They used to be stringified here and
  re-parsed by every consumer.
- **`s2t` is a real JSON array.** It used to be `str(payload["s2t"])`, i.e. a
  Python repr with single quotes that no JSON parser accepts.
- **`object` and `return_object` are gone** (doc comment [k]). The field was
  empty on all 872,631 indexed points.
- **`frame_path` / `video_path` are gone** (doc comments [p]/[t]). Records carry
  identifiers only; clients build media URLs from `GET /hub/media_config`.
- **Scroll results carry `score: 0.0`**, not the previous fabricated `"0.273"`.

### Building media URLs

`GET /hub/media_config` returns the dataset layout rule:

```json
{
  "image_base_url": "http://<host>:9027/img",
  "video_base_url": "http://<host>:9027/video",
  "frame_template": "{batch}/frames/{split}/Keyframes_{prefix}/keyframes/{video}/{keyframe}{ext}",
  "video_template": "{batch}/videos/Videos_{prefix}/video/{video}.mp4",
  "split": "low_res_autoshot",
  "split_original": "low_res_autoshot",
  "frame_ext": ".avif",
  "keyframe_pad": 5
}
```

Substitute `batch` = `idx_folder`, `video` = `video_name` without its extension,
`prefix` = the part before the first underscore, `keyframe` = `keyframe_id`
zero-padded to `keyframe_pad`. `src/utils/dataset_layout.py` owns this rule
server-side; nothing else should hardcode a copy.

## Hub API (recommended client API)

Base URL: `http://<host>:9021/hub`.

### Retrieval

All retrieval operations use **`POST /search`** with form-data. Its successful
response is the common response envelope with a list of ranked frame records
in `data`. `model` is a configured registry key; the built-in fallback keys
are `siglip_alpha`, `siglip_beta`, and `metaclip`.

Shared optional form fields:

| Field | Type / default | Meaning |
| --- | --- | --- |
| `k` | integer, `100` | Maximum results. |
| `video_filter` | string or omitted | Limit to a video or video filter expression. |
| `s2t_filter` | string or omitted | Limit by speech-to-text content. |
| `time_in`, `time_out` | string or omitted | Time-range filter. |
| `return_s2t` | boolean, `true` | Include transcript payload. |
| `frame_class_filter` | JSON string, `[]` | Frame-class IDs, for example `[1, 4]`. |
| `skip_frames` | JSON string, `[]` | Frames/ranges to omit. |
| `sort_to_news` | boolean, `true` | Apply the service's news-oriented result ordering. |
| `model` | string | Required model-registry key. |
| `search_type` | `text`, `image`, `temporal`, or `scroll` | Required operation selector. |

| `search_type` | Required fields | Additional fields | Purpose |
| --- | --- | --- | --- |
| `text` | `text` | shared fields | Text-to-frame search. |
| `image` | `image_path` | shared fields | Search by a readable image path. |
| `temporal` | `text` | shared fields, `main_event_index` | Text search with temporal-event handling. |
| `scroll` | `video_filter` | `k`, time/filter/return fields, `utility_feature` | Browse frames from a selected video/filter. |

`main_event_index` is an integer with default `0`.  `utility_feature` defaults
to `shot` for scroll.  `image_path` is a server-readable path, not base64 image
content; it must be accessible to the hub container.

Example text search:

```bash
curl -X POST http://<host>:9021/hub/search \
  -F 'model=siglip_alpha' \
  -F 'search_type=text' \
  -F 'text=a red car driving on a city street' \
  -F 'k=10' \
  -F 'return_s2t=true' \
  -F 'frame_class_filter=[]'
```

Example image search:

```bash
curl -X POST http://<host>:9021/hub/search \
  -F 'model=siglip_alpha' \
  -F 'search_type=image' \
  -F 'image_path=/app/data/query/example.jpg' \
  -F 'k=10' \
  -F 'return_s2t=true' \
  -F 'frame_class_filter=[]'
```

`image_path` may also be a `data:image/...` URI or an HTTP(S) image URL, as
long as the hub container can read it.

Example temporal search:

```bash
curl -X POST http://<host>:9021/hub/search \
  -F 'model=siglip_alpha' \
  -F 'search_type=temporal' \
  -F 'text=a person enters a room. Then the person sits at a desk.' \
  -F 'main_event_index=0' \
  -F 'k=10' \
  -F 'return_s2t=true' \
  -F 'frame_class_filter=[]'
```

Example scroll search:

```bash
curl -X POST http://<host>:9021/hub/search \
  -F 'model=siglip_alpha' \
  -F 'search_type=scroll' \
  -F 'video_filter=L28_V009' \
  -F 'time_in=1000' \
  -F 'time_out=5000' \
  -F 'utility_feature=shot' \
  -F 'k=20'
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
      "index": 0
    }
  ]
}
```

### Result export

`POST /hub/download` renders the current result set as a submission CSV
(doc comment [l]). It takes the same fields as `POST /hub/search`, plus:

- `format` (`kis` | `trake`, default `kis`)
- `limit` (integer, default `100`)

It is **stateless** — it re-runs the query rather than reading a cached "current
search", because the hub serves requests from several worker processes.

`kis` emits one `video,keyframe` per row; `trake` emits one row per video as
`video,frame1,frame2,...`. Neither format has a header row.

```bash
curl -X POST http://<host>:9021/hub/download \
  -F 'model=siglip_alpha' \
  -F 'search_type=text' \
  -F 'text=a red car driving on a city street' \
  -F 'format=kis' -F 'limit=100'
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
`keyframe_id`, `fps`, `score`, `s2t`, and `index`.  The direct reranker is only
usable when its supporting rerank
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
