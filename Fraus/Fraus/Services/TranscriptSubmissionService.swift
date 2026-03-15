import Foundation

struct TranscriptMessagePayload: Codable {
    let speaker: String
    let text: String
}

struct SubmitTranscriptRequestPayload: Codable {
    let callerNumber: String
    let calleeNumber: String
    let callerLabel: String?
    let riskLevel: String?
    let sessionId: String?
    let messages: [TranscriptMessagePayload]

    enum CodingKeys: String, CodingKey {
        case callerNumber = "caller_number"
        case calleeNumber = "callee_number"
        case callerLabel = "caller_label"
        case riskLevel = "risk_level"
        case sessionId = "session_id"
        case messages
    }
}

struct SubmitTranscriptResponsePayload: Codable {
    let transcriptId: String
    let status: String
    let message: String

    enum CodingKeys: String, CodingKey {
        case transcriptId = "transcript_id"
        case status
        case message
    }
}

final class TranscriptSubmissionService {
    private let baseURL: URL
    private let session: URLSession

    init(
        baseURL: URL = AppRuntimeConfiguration.verificationBaseURL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    func submit(
        callerNumber: String,
        callerLabel: String?,
        riskLevel: String?,
        sessionId: String?,
        messages: [ConversationTimelineMessage]
    ) async {
        let payloadMessages = messages.map { msg in
            TranscriptMessagePayload(
                speaker: msg.speaker.rawValue,
                text: msg.text
            )
        }

        let payload = SubmitTranscriptRequestPayload(
            callerNumber: callerNumber,
            calleeNumber: "unknown",
            callerLabel: callerLabel,
            riskLevel: riskLevel,
            sessionId: sessionId,
            messages: payloadMessages
        )

        let endpoint = baseURL.appendingPathComponent("submit-transcript")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 10

        do {
            request.httpBody = try JSONEncoder().encode(payload)
            let (data, response) = try await session.data(for: request)

            if let httpResponse = response as? HTTPURLResponse {
                if (200...299).contains(httpResponse.statusCode) {
                    if let decoded = try? JSONDecoder().decode(SubmitTranscriptResponsePayload.self, from: data) {
                        print("[TranscriptSubmission] Success: \(decoded.transcriptId) — \(decoded.status)")
                    }
                } else {
                    print("[TranscriptSubmission] Server returned \(httpResponse.statusCode)")
                }
            }
        } catch {
            print("[TranscriptSubmission] Failed to send transcript: \(error.localizedDescription)")
        }
    }
}
