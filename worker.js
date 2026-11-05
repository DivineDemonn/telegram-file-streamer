export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Change ONLY this domain if you ever switch to a new Render account or hosting server
    const ACTIVE_BACKEND = "telegram-file-streamer-3vsl.onrender.com";

    url.hostname = ACTIVE_BACKEND;
    url.protocol = "https:";

    const newRequest = new Request(url.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: "follow"
    });

    return fetch(newRequest);
  }
};
