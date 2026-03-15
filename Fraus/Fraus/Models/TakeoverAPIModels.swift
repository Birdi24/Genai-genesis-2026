import Foundation

struct StartTakeoverRequest: Codable {
    let phoneNumber: String
    let callerLabel: String?
    let riskLevel: String?

    enum CodingKeys: String, CodingKey {
        case phoneNumber = "phone_number"
        case callerLabel = "caller_label"
        case riskLevel = "risk_level"
    }

    init(phoneNumber: String, callerLabel: String?, riskLevel: String?) {
        self.phoneNumber = phoneNumber.trimmingCharacters(in: .whitespacesAndNewlines)

        let normalizedCallerLabel = callerLabel?.trimmingCharacters(in: .whitespacesAndNewlines)
        self.callerLabel = (normalizedCallerLabel?.isEmpty == false) ? normalizedCallerLabel : nil

        let normalizedRiskLevel = riskLevel?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        self.riskLevel = (normalizedRiskLevel?.isEmpty == false) ? normalizedRiskLevel : nil
    }
}

struct StartTakeoverResponse: Codable {
    let sessionID: String

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
    }
}

struct TakeoverSessionEventRequestPayload: Codable {
    let eventType: String
    let source: String
    let role: String?
    let text: String?
    let metadata: [String: String]
    let occurredAt: String?

    enum CodingKeys: String, CodingKey {
        case eventType = "event_type"
        case source
        case role
        case text
        case metadata
        case occurredAt = "occurred_at"
    }
}

struct TakeoverSessionResponse: Codable {
    let sessionID: String
    let phoneNumber: String
    let callerLabel: String?
    let statusText: String
    let connectionState: ProtectionConnectionState
    let conversationSignedURL: URL?
    let aiAgentName: String?
    let startedAt: Date?
    let transcriptNotes: [String]
    let scamIndicators: [String]
    let extractedEntities: [TakeoverSessionEntityResponse]
    let businessIntelligenceSteps: [String]

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case phoneNumber = "phone_number"
        case callerLabel = "caller_label"
        case statusText = "status_text"
        case connectionState = "connection_state"
        case conversationSignedURL = "conversation_signed_url"
        case aiAgentName = "ai_agent_name"
        case startedAt = "started_at"
        case transcriptNotes = "transcript_notes"
        case scamIndicators = "scam_indicators"
        case extractedEntities = "extracted_entities"
        case businessIntelligenceSteps = "business_intelligence_steps"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sessionID = try container.decode(String.self, forKey: .sessionID)
        phoneNumber = (try container.decodeIfPresent(String.self, forKey: .phoneNumber)) ?? ""

        let rawCallerLabel = try container.decodeIfPresent(String.self, forKey: .callerLabel)
        callerLabel = rawCallerLabel?.trimmingCharacters(in: .whitespacesAndNewlines)

        let rawStatus = (try container.decodeIfPresent(String.self, forKey: .statusText)) ?? ""
        let sanitizedStatus = rawStatus.trimmingCharacters(in: .whitespacesAndNewlines)
        let rawConnectionState = (try container.decodeIfPresent(String.self, forKey: .connectionState)) ?? "degraded"
        connectionState = ProtectionConnectionState(rawValue: rawConnectionState) ?? .degraded

        if let signedURL = try container.decodeIfPresent(String.self, forKey: .conversationSignedURL),
           let parsedURL = URL(string: signedURL) {
            conversationSignedURL = parsedURL
        } else {
            conversationSignedURL = nil
        }

        statusText = sanitizedStatus.isEmpty ? connectionState.fallbackStatusText : sanitizedStatus

        let rawAgent = try container.decodeIfPresent(String.self, forKey: .aiAgentName)
        aiAgentName = rawAgent?.trimmingCharacters(in: .whitespacesAndNewlines)

        if let startedAtString = try container.decodeIfPresent(String.self, forKey: .startedAt) {
            startedAt = TakeoverDateParser.parse(startedAtString)
        } else {
            startedAt = nil
        }

        transcriptNotes = ((try container.decodeIfPresent([String].self, forKey: .transcriptNotes)) ?? [])
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        scamIndicators = ((try container.decodeIfPresent([String].self, forKey: .scamIndicators)) ?? [])
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        extractedEntities = (try container.decodeIfPresent([TakeoverSessionEntityResponse].self, forKey: .extractedEntities)) ?? []

        businessIntelligenceSteps = ((try container.decodeIfPresent([String].self, forKey: .businessIntelligenceSteps)) ?? [])
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }
}

struct TakeoverSessionEntityResponse: Codable {
    let key: String
    let value: String
    let confidence: Int

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        key = (try container.decodeIfPresent(String.self, forKey: .key))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "Unknown Field"
        value = (try container.decodeIfPresent(String.self, forKey: .value))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "Unavailable"

        if let integerConfidence = try? container.decode(Int.self, forKey: .confidence) {
            confidence = integerConfidence
        } else if let doubleConfidence = try? container.decode(Double.self, forKey: .confidence) {
            if doubleConfidence <= 1 {
                confidence = Int((doubleConfidence * 100).rounded())
            } else {
                confidence = Int(doubleConfidence.rounded())
            }
        } else {
            confidence = 0
        }
    }
}

extension TakeoverSessionResponse {
    func toProtectionSession(
        callCategory: DemoCallCategory?,
        sourceCallSessionID: UUID?,
        sessionStartTime: Date,
        fallbackSession: ProtectionSession? = nil
    ) -> ProtectionSession {
        let normalizedPhone = phoneNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        let resolvedPhoneNumber: String
        if !normalizedPhone.isEmpty {
            resolvedPhoneNumber = normalizedPhone
        } else if let fallbackSession {
            resolvedPhoneNumber = fallbackSession.callerNumber
        } else {
            resolvedPhoneNumber = "Unknown Number"
        }

        let resolvedStartTime = startedAt ?? fallbackSession?.sessionStartTime ?? sessionStartTime

        let resolvedTranscriptNotes = transcriptNotes.isEmpty ? (fallbackSession?.transcriptNotes ?? []) : transcriptNotes
        let resolvedScamIndicators = scamIndicators.isEmpty ? (fallbackSession?.scamIndicators ?? []) : scamIndicators

        let mappedEntities = extractedEntities.map {
            SessionEntity(
                key: $0.key,
                value: $0.value,
                confidence: min(max($0.confidence, 0), 100)
            )
        }

        let resolvedEntities = mappedEntities.isEmpty ? (fallbackSession?.extractedEntities ?? []) : mappedEntities
        let resolvedBISteps = businessIntelligenceSteps.isEmpty ? (fallbackSession?.businessIntelligenceSteps ?? []) : businessIntelligenceSteps

        return ProtectionSession(
            sessionID: sessionID,
            callerNumber: resolvedPhoneNumber,
            callerLabel: callerLabel ?? fallbackSession?.callerLabel,
            callCategory: callCategory,
            aiAgentName: aiAgentName ?? fallbackSession?.aiAgentName ?? "Fraus Sentinel v1",
            statusText: statusText,
            connectionState: connectionState,
            signedConversationURL: conversationSignedURL ?? fallbackSession?.signedConversationURL,
            sourceCallSessionID: sourceCallSessionID,
            sessionStartTime: resolvedStartTime,
            transcriptNotes: resolvedTranscriptNotes,
            scamIndicators: resolvedScamIndicators,
            extractedEntities: resolvedEntities,
            businessIntelligenceSteps: resolvedBISteps
        )
    }
}

private enum TakeoverDateParser {
    private static let primaryFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let fallbackFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    static func parse(_ value: String) -> Date? {
        primaryFormatter.date(from: value) ?? fallbackFormatter.date(from: value)
    }
}
