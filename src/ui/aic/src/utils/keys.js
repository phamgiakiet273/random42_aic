/** Enter that is really "submit". While an input method is composing (the
 *  Vietnamese IME on macOS holds each word in composition), Enter only commits
 *  the word: acting on it would search / SUBMIT the half-typed text. Safari
 *  reports that Enter with keyCode 229 instead of isComposing. */
export function isEnter(e) {
  return e.key === 'Enter' && !e.nativeEvent?.isComposing && e.keyCode !== 229
}
