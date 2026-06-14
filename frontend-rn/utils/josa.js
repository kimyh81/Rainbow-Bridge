// 한글 받침(종성) 유무에 따라 조사를 자동으로 골라주는 유틸
// 펫 이름이 받침으로 끝나면 '과/이/을/은', 아니면 '와/가/를/는'

// 마지막 글자에 받침이 있는지 판별
function hasBatchim(word) {
  if (!word) return false;
  const last = String(word).trim().slice(-1);
  const code = last.charCodeAt(0);
  // 한글 음절(가~힣)이 아니면 받침 없음으로 취급 (영문/숫자 등)
  if (code < 0xac00 || code > 0xd7a3) return false;
  return (code - 0xac00) % 28 !== 0;
}

// 와 / 과
export function gwa(word) {
  return hasBatchim(word) ? '과' : '와';
}

// 이 / 가
export function iga(word) {
  return hasBatchim(word) ? '이' : '가';
}

// 을 / 를
export function eulreul(word) {
  return hasBatchim(word) ? '을' : '를';
}

// 은 / 는
export function eunneun(word) {
  return hasBatchim(word) ? '은' : '는';
}
