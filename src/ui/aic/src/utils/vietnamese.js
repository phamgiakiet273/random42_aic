// Letters only Vietnamese uses (same set as src/modules/translate/vinai.py). Text
// without any is English already: it is never sent for translation.
const VIETNAMESE = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i

export const hasVietnamese = (text) => VIETNAMESE.test(text || '')
