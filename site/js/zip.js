// Minimal zip reader: finds the chat .txt inside a WhatsApp export and inflates it with the
// browser's built-in DecompressionStream. No libraries, nothing uploaded.

const td = new TextDecoder("utf-8");

export function isZip(bytes) {
  return bytes[0] === 0x50 && bytes[1] === 0x4b && bytes[2] === 0x03 && bytes[3] === 0x04;
}

function entries(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  // End of central directory: last 22+ bytes, signature 0x06054b50
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) {
    if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("This zip file looks damaged");
  const count = view.getUint16(eocd + 10, true);
  let p = view.getUint32(eocd + 16, true);
  const list = [];
  for (let n = 0; n < count; n++) {
    if (view.getUint32(p, true) !== 0x02014b50) throw new Error("This zip file looks damaged");
    const method = view.getUint16(p + 10, true);
    const compSize = view.getUint32(p + 20, true);
    const nameLen = view.getUint16(p + 28, true);
    const extraLen = view.getUint16(p + 30, true);
    const commentLen = view.getUint16(p + 32, true);
    const localOffset = view.getUint32(p + 42, true);
    const name = td.decode(bytes.subarray(p + 46, p + 46 + nameLen));
    list.push({ name, method, compSize, localOffset });
    p += 46 + nameLen + extraLen + commentLen;
  }
  return { list, view };
}

async function inflate(data) {
  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** Return the text of the chat file inside a zip export. */
export async function chatFromZip(bytes) {
  const { list, view } = entries(bytes);
  const txts = list.filter((e) => e.name.toLowerCase().endsWith(".txt"));
  if (!txts.length) throw new Error("No .txt chat file inside this zip");
  const e = txts.find((t) => t.name.toLowerCase().includes("chat")) || txts[0];
  const nameLen = view.getUint16(e.localOffset + 26, true);
  const extraLen = view.getUint16(e.localOffset + 28, true);
  const start = e.localOffset + 30 + nameLen + extraLen;
  const data = bytes.subarray(start, start + e.compSize);
  if (e.method === 0) return td.decode(data);
  if (e.method === 8) return td.decode(await inflate(data));
  throw new Error("Unsupported zip compression");
}
