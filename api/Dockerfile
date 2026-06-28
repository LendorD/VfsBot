# Go-бэкенд (server + bot). Контекст сборки — КОРЕНЬ проекта.
FROM golang:1.22 AS build
WORKDIR /src
COPY api/ ./
RUN go mod tidy && \
    CGO_ENABLED=0 go build -o /out/server ./cmd/server && \
    CGO_ENABLED=0 go build -o /out/bot ./cmd/bot

FROM alpine:3.20
WORKDIR /app
COPY --from=build /out/server /app/server
COPY --from=build /out/bot /app/bot
COPY frontend /app/frontend
ENV FRONTEND_DIR=/app/frontend
EXPOSE 8000
CMD ["/app/server"]
