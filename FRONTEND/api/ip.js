export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const forwarded = req.headers['x-forwarded-for'];
  const ip = forwarded ? forwarded.split(',')[0] : req.socket?.remoteAddress || '47.29.188.162';
  res.status(200).json({ ip });
}
