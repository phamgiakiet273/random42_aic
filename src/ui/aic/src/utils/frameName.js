export function cleanFrameName(frameName) {
  return (frameName || '').split('.')[0]
}
