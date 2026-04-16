const TARGET = "https://petal-insight.juzibot.com";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = TARGET + url.pathname + url.search;

    const headers = new Headers(request.headers);
    headers.set("Host", "petal-insight.juzibot.com");
    headers.delete("cf-connecting-ip");
    headers.delete("cf-ipcountry");
    headers.delete("cf-ray");
    headers.delete("cf-visitor");
    headers.delete("x-forwarded-for");
    headers.delete("x-forwarded-proto");
    headers.delete("x-real-ip");

    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (!["GET", "HEAD"].includes(request.method)) {
      init.body = request.body;
    }

    const upstream = await fetch(target, init);

    const respHeaders = new Headers(upstream.headers);
    respHeaders.delete("content-encoding");
    respHeaders.delete("content-length");
    respHeaders.delete("transfer-encoding");

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  },
};
