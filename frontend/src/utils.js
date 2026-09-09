export function formatTime(seconds) {
  const s = Math.max(0, Number(seconds) || 0)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function formatDate(value) {
  if (!value) return ''
  return new Date(value.replace(' ', 'T')).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

// Counts are stored raw with their level total alongside. Runs recorded before
// the totals existed have total = 0: show the bare count rather than "87/0".
export function ratio(done, total) {
  return total ? `${done ?? 0}/${total}` : `${done ?? 0}`
}
