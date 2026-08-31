// Hub API calls. One consolidated POST /hub/search covers every search type
// (doc comments [c]/[n]) — `model` picks the backend, `search_type` the mode.
import { postForm, postFormRaw, get } from './client'

export const SEARCH_TYPES = {
  TEXT: 'text',
  IMAGE: 'image',
  TEMPORAL: 'temporal',
  SCROLL: 'scroll',
}

// scroll_video accepts exactly these three and raises on anything else.
//   shot   - a shot's frames (time_in/out = related_start/end_frame), or a
//            whole video when no bounds are given
//   dup    - duplicates of one frame (time_in = time_out = keyframe_id)
//   unique - the unique counterpart of one frame
export const UTILITY_FEATURES = {
  SHOT: 'shot',
  DUP: 'dup',
  UNIQUE: 'unique',
}

// Only siglip_alpha has a populated Qdrant collection on this deployment.
// siglip_beta / metaclip / fusion_model are configured but have no index, so
// they are listed as unavailable rather than offered and then failing.
export const MODELS = [
  { value: 'siglip_alpha', label: 'SigLIP2 Alpha', available: true },
  { value: 'siglip_beta', label: 'SigLIP2 Beta', available: false },
  { value: 'metaclip', label: 'MetaCLIP', available: false },
  { value: 'fusion_model', label: 'Fusion (SigLIP2 + Jina)', available: false },
]

export const DEFAULT_MODEL = 'siglip_alpha'

function searchFields({
  model = DEFAULT_MODEL,
  searchType,
  text,
  imagePath,
  k = 100,
  videoFilter,
  s2tFilter,
  timeIn,
  timeOut,
  returnS2t = true,
  frameClassFilter = [],
  skipFrames = [],
  sortToNews = true,
  mainEventIndex = 0,
  utilityFeature = 'shot',
}) {
  return {
    model,
    search_type: searchType,
    text,
    image_path: imagePath,
    k,
    video_filter: videoFilter,
    s2t_filter: s2tFilter,
    time_in: timeIn,
    time_out: timeOut,
    return_s2t: returnS2t,
    frame_class_filter: frameClassFilter,
    skip_frames: skipFrames,
    sort_to_news: sortToNews,
    main_event_index: mainEventIndex,
    utility_feature: utilityFeature,
  }
}

/** Run a search -> { records, chains }. Temporal returns chains (one array per
 *  matched event sequence); they are flattened, tagged with chainId /
 *  chainPosition, and also returned intact. */
export async function runSearch(params) {
  const data = await postForm('/hub/search', searchFields(params))
  const rows = Array.isArray(data) ? data : []

  if (rows.length && Array.isArray(rows[0])) {
    const chains = rows
    const records = []
    chains.forEach((chain, chainId) => {
      chain.forEach((frame, chainPosition) => {
        records.push({ ...frame, chainId, chainPosition, chainLength: chain.length })
      })
    })
    return { records, chains }
  }
  return { records: rows, chains: null }
}

/** Params for a per-record scroll. `dup`/`unique` address one frame, so both
 *  bounds carry its keyframe id; `shot` spans the record's shot. */
export function utilityScrollParams(record, feature, base = {}) {
  const isFrameAddressed =
    feature === UTILITY_FEATURES.DUP || feature === UTILITY_FEATURES.UNIQUE
  const frameId = parseInt(record.keyframe_id, 10)
  return {
    ...base,
    searchType: SEARCH_TYPES.SCROLL,
    videoFilter: String(record.video_name ?? '').split('.')[0],
    utilityFeature: feature,
    timeIn: isFrameAddressed ? frameId : parseInt(record.related_start_frame, 10),
    timeOut: isFrameAddressed ? frameId : parseInt(record.related_end_frame, 10),
    // A whole segment, not a ranked list -- legacy used the same figure.
    k: 2000,
  }
}

/** Frames around a given frame in the same video (hub -> util service). */
export async function getNeighboringFrames(videoName, frameNum, k = 5) {
  return postForm('/hub/get_neighboring_frames', {
    video_name: videoName,
    frame_num: frameNum,
    k,
  })
}

/** Video names (and their batch prefixes) for the given dataset batches. */
export async function getVideoNames(batchIds = [0, 1]) {
  const data = await postForm('/hub/get_video_names_of_batch', { batch_id: batchIds })
  return Array.isArray(data) ? data : []
}

export function getMediaConfig() {
  return get('/hub/media_config')
}

/** Server-rendered submission CSV (doc comment [l]). Stateless: the hub
 *  re-runs `params`, since it serves from several worker processes. */
export async function downloadResultCsv(params, { format = 'kis', limit = 100 } = {}) {
  const res = await postFormRaw('/hub/download', {
    ...searchFields(params),
    format,
    limit,
    return_s2t: false,
  })
  const text = await res.text()
  const match = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') || '')
  return { text, filename: match?.[1] || `result_${format}.csv` }
}

export function translate(text, { source = '', target = 'en' } = {}) {
  return postForm('/hub/translate', { text, source, target })
}
