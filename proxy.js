// Minimal authenticated HTTP forward proxy with CONNECT support.
// For use as a private egress relay. Requires Basic auth on every request.
const http = require('http');
const net = require('net');
const { URL } = require('url');

const PORT = process.env.PORT || 8080;
const USER = process.env.PROXY_USER || '';
const PASS = process.env.PROXY_PASS || '';

if (!USER || !PASS) {
  console.error('PROXY_USER and PROXY_PASS must be set');
  process.exit(1);
}
const EXPECTED = 'Basic ' + Buffer.from(`${USER}:${PASS}`).toString('base64');

function authed(req) {
  return (req.headers['proxy-authorization'] || '') === EXPECTED;
}
function deny(res) {
  res.writeHead(407, { 'Proxy-Authenticate': 'Basic realm="proxy"' });
  res.end('Proxy authentication required');
}

// Plain HTTP proxying
const server = http.createServer((req, res) => {
  if (req.url === '/healthz') { res.writeHead(200); res.end('ok'); return; }
  if (!authed(req)) return deny(res);
  let target;
  try { target = new URL(req.url); } catch { res.writeHead(400); res.end('bad url'); return; }
  const headers = { ...req.headers };
  delete headers['proxy-authorization'];
  headers.host = target.host;
  const up = http.request({
    hostname: target.hostname,
    port: target.port || 80,
    path: target.pathname + target.search,
    method: req.method,
    headers,
  }, (upRes) => {
    res.writeHead(upRes.statusCode, upRes.headers);
    upRes.pipe(res);
  });
  up.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('upstream error'); });
  req.pipe(up);
});

// HTTPS tunneling
server.on('connect', (req, clientSocket, head) => {
  if (!authed(req)) {
    clientSocket.write('HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="proxy"\r\n\r\n');
    clientSocket.destroy();
    return;
  }
  const [host, portStr] = req.url.split(':');
  const port = parseInt(portStr, 10) || 443;
  const upstream = net.connect(port, host, () => {
    clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
    if (head && head.length) upstream.write(head);
    upstream.pipe(clientSocket);
    clientSocket.pipe(upstream);
  });
  upstream.on('error', () => clientSocket.destroy());
  clientSocket.on('error', () => upstream.destroy());
});

server.listen(PORT, () => console.log(`proxy listening on ${PORT}`));
