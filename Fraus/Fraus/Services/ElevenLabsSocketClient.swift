import Foundation

enum ElevenLabsSocketConnectionState: Equatable {
    case idle
    case connecting
    case connected
    case failed
    case closed
}

enum ElevenLabsSocketEvent: Equatable {
    case userTranscript(text: String, eventID: String?)
    case agentResponse(text: String, eventID: String?)
    case agentResponseCorrection(text: String, correctedEventID: String?)
    case agentChatResponsePart(text: String, responseID: String?)
    case audio(sequence: Int?, eventID: String?)
    case ping(eventID: String?)
    case pong(eventID: String?)
    case state(String)
    case error(String)
    case control(String)
}

enum ElevenLabsSocketEventParser {
    static func parse(object: [String: Any]) -> [ElevenLabsSocketEvent] {
        let type = normalizedType(from: object)
        let eventID = stringValue(for: ["event_id", "eventId", "id"], in: object)

        switch type {
        case "user_transcript":
            guard let text = textValue(in: object, keys: ["user_transcript", "transcript", "text"]) else {
                return []
            }
            return [.userTranscript(text: text, eventID: eventID)]

        case "agent_chat_response_part":
            guard let text = textValue(in: object, keys: ["agent_chat_response_part", "delta", "text"]) else {
                return []
            }
            return [.agentChatResponsePart(text: text, responseID: eventID)]

        case "agent_response":
            guard let text = textValue(in: object, keys: ["agent_response", "text"]) else {
                return []
            }
            return [.agentResponse(text: text, eventID: eventID)]

        case "agent_response_correction":
            guard let text = textValue(in: object, keys: ["agent_response_correction", "corrected_text", "text"]) else {
                return []
            }
            let correctedEventID = stringValue(for: ["corrected_event_id", "target_event_id", "event_id"], in: object)
            return [.agentResponseCorrection(text: text, correctedEventID: correctedEventID)]

        case "audio":
            return [
                .audio(
                    sequence: intValue(for: ["sequence", "seq"], in: object),
                    eventID: eventID
                )
            ]

        case "ping":
            return [.ping(eventID: eventID)]

        case "pong":
            return [.pong(eventID: eventID)]

        default:
            if type.contains("error") {
                let message = textValue(in: object, keys: ["message", "error", "text"]) ?? type
                return [.error(message)]
            }

            if type.contains("state") || type.contains("conversation") {
                return [.state(type)]
            }

            if type.contains("transcript"),
               let text = textValue(in: object, keys: ["transcript", "text"]) {
                return [.userTranscript(text: text, eventID: eventID)]
            }

            return [.control(type)]
        }
    }

    private static func normalizedType(from object: [String: Any]) -> String {
        let type = (object["type"] as? String) ?? "unknown"
        return type.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    private static func textValue(in object: [String: Any], keys: [String]) -> String? {
        for key in keys {
            if let value = object[key] as? String {
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    return trimmed
                }
            }
        }

        for nestedKey in ["message", "payload", "data"] {
            guard let nested = object[nestedKey] as? [String: Any] else { continue }
            for key in keys {
                if let value = nested[key] as? String {
                    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty {
                        return trimmed
                    }
                }
            }
        }

        return nil
    }

    private static func stringValue(for keys: [String], in object: [String: Any]) -> String? {
        for key in keys {
            if let value = object[key] as? String {
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    return trimmed
                }
            }
            if let number = object[key] as? NSNumber {
                return number.stringValue
            }
        }
        return nil
    }

    private static func intValue(for keys: [String], in object: [String: Any]) -> Int? {
        for key in keys {
            if let value = object[key] as? Int {
                return value
            }
            if let number = object[key] as? NSNumber {
                return number.intValue
            }
            if let text = object[key] as? String, let parsed = Int(text) {
                return parsed
            }
        }
        return nil
    }
}

protocol ElevenLabsSocketClienting: AnyObject {
    var onConnectionStateChange: ((ElevenLabsSocketConnectionState) -> Void)? { get set }
    var onEvent: ((ElevenLabsSocketEvent) -> Void)? { get set }

    func connect()
    func sendAudioChunk(base64Chunk: String, sequence: Int, isFinal: Bool)
    func disconnect()
}

final class ElevenLabsSocketClient: ElevenLabsSocketClienting {
    var onConnectionStateChange: ((ElevenLabsSocketConnectionState) -> Void)?
    var onEvent: ((ElevenLabsSocketEvent) -> Void)?

    private let signedURL: URL
    private let session: URLSession
    private var socketTask: URLSessionWebSocketTask?
    private var hasEmittedConnected = false
    private var hasSeenInboundMessage = false

    init(signedURL: URL, session: URLSession = .shared) {
        self.signedURL = signedURL
        self.session = session
    }

    func connect() {
        log("connect attempt started: \(signedURL.absoluteString.prefix(160))")
        onConnectionStateChange?(.connecting)

        let socketTask = session.webSocketTask(with: signedURL)
        self.socketTask = socketTask
        hasEmittedConnected = false
        hasSeenInboundMessage = false
        socketTask.resume()

        receiveLoop()
        sendConversationInitIfNeeded()
    }

    func disconnect() {
        if let socketTask {
            log("socket closing with code normalClosure")
            socketTask.cancel(with: .normalClosure, reason: nil)
        }
        socketTask?.cancel(with: .normalClosure, reason: nil)
        socketTask = nil
        onConnectionStateChange?(.closed)
    }

    func sendAudioChunk(base64Chunk: String, sequence: Int, isFinal: Bool) {
        guard let socketTask else { return }
        let payload: [String: Any] = [
            "type": "user_audio_chunk",
            "audio_base_64": base64Chunk,
            "sequence": sequence,
            "is_final": isFinal
        ]
        sendJSONObject(payload, on: socketTask)
    }

    private func sendConversationInitIfNeeded() {
        guard let socketTask else { return }
        let payload: [String: Any] = [
            "type": "conversation_initiation_client_data",
            "conversation_config_override": [
                "agent": [:]
            ]
        ]

        sendJSONObject(payload, on: socketTask) { [weak self] error in
            guard let self else { return }
            if let error {
                self.log("conversation init send failed: \(error.localizedDescription)")
                self.onConnectionStateChange?(.failed)
                return
            }
            self.emitConnectedIfNeeded(reason: "conversation_init_sent")
            self.log("conversation init sent")
        }
    }

    private func sendJSONObject(
        _ payload: [String: Any],
        on socketTask: URLSessionWebSocketTask,
        completion: ((Error?) -> Void)? = nil
    ) {
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else {
            completion?(NSError(domain: "ElevenLabsSocketClient", code: -1))
            return
        }

        socketTask.send(.string(text)) { error in
            completion?(error)
        }
    }

    private func receiveLoop() {
        socketTask?.receive { [weak self] result in
            guard let self else { return }

            switch result {
            case .success(let message):
                self.emitConnectedIfNeeded(reason: "first_inbound_message")
                self.handle(message)
                self.receiveLoop()
            case .failure(let error):
                self.log("socket receive failed: \(error.localizedDescription)")
                self.onEvent?(.control("socket_receive_error:\(error.localizedDescription)"))
                self.onConnectionStateChange?(.failed)
            }
        }
    }

    private func handle(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            if !hasSeenInboundMessage {
                hasSeenInboundMessage = true
                log("first inbound event raw text received")
            }
            guard let data = text.data(using: .utf8),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                onEvent?(.control(text))
                return
            }
            handleJSONEvent(object)
        case .data(let data):
            if !hasSeenInboundMessage {
                hasSeenInboundMessage = true
                log("first inbound binary message received")
            }
            onEvent?(.control("binary_data_received_\(data.count)bytes"))
        @unknown default:
            break
        }
    }

    private func handleJSONEvent(_ object: [String: Any]) {
        let events = ElevenLabsSocketEventParser.parse(object: object)

        for event in events {
            switch event {
            case .ping(let eventID):
                sendPong(eventID: eventID)
                onEvent?(.ping(eventID: eventID))
            default:
                log("inbound event parsed: \(event)")
                onEvent?(event)
            }
        }
    }

    private func sendPong(eventID: String?) {
        guard let socketTask else { return }

        var payload: [String: Any] = ["type": "pong"]
        if let eventID {
            payload["event_id"] = eventID
        }
        sendJSONObject(payload, on: socketTask)
    }

    private func emitConnectedIfNeeded(reason: String) {
        guard !hasEmittedConnected else { return }
        hasEmittedConnected = true
        log("socket open/connected via \(reason)")
        onConnectionStateChange?(.connected)
    }

    private func log(_ message: String) {
        print("[ElevenLabsSocketClient] \(message)")
    }
}
