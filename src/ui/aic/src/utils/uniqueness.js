// A thin card outline from `is_unique`, which every search result already carries
// (a Qdrant payload field written at ingest): nothing is loaded for it here, and no
// per-search file read happens on the server. An outline, not a fill: the user
// found tinted cards too distracting.
//   unique              green
//   repeated elsewhere  yellow, stronger: near-identical frames occur on other
//                       occasions, so a submit may name the wrong moment
// Records without the field (e.g. result-manager CSV rows) get no outline.
export function uniquenessStyle(isUnique) {
  if (isUnique === true) return { outline: 'outline outline-green-500/65', label: 'Unique frame' }
  if (isUnique === false) {
    return {
      outline: 'outline outline-yellow-400/80',
      label: 'Repeated frame: near-identical frames appear on other occasions. Check it is the right moment before submitting',
    }
  }
  return { outline: '', label: undefined }
}
