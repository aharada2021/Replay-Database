function handler(event) {
    var request = event.request;
    var headers = request.headers;

    // Base64 encoded credentials: ozeki:onakasuita
    var authString = "Basic b3pla2k6b25ha2FzdWl0YQ==";

    if (
        typeof headers.authorization === "undefined" ||
        headers.authorization.value !== authString
    ) {
        return {
            statusCode: 401,
            statusDescription: "Unauthorized",
            headers: {
                "www-authenticate": { value: "Basic realm=\"WoWS Replay\"" }
            }
        };
    }

    return request;
}
