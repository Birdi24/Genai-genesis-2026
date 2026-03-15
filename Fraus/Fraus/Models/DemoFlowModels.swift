import Foundation

enum DemoCallCategory: String, Hashable {
    case scam
    case unknown

    var title: String {
        switch self {
        case .scam:
            return "Scam"
        case .unknown:
            return "Unknown"
        }
    }
}

enum DemoCallStatus: String, Hashable {
    case incoming
    case verifying
    case verified
    case suspicious
    case transferred
    case activeProtection
    case completed

    var title: String {
        switch self {
        case .incoming:
            return "Incoming"
        case .verifying:
            return "Verifying"
        case .verified:
            return "Verified"
        case .suspicious:
            return "Suspicious"
        case .transferred:
            return "Transferred to AI"
        case .activeProtection:
            return "Active Protection"
        case .completed:
            return "Completed"
        }
    }
}

struct DemoCallSession: Hashable, Identifiable {
    let id: UUID
    let phoneNumber: String
    let callerLabel: String
    let callCategory: DemoCallCategory
    let status: DemoCallStatus
    let transcriptLines: [String]
    let transferredToAI: Bool
    let startTime: Date

    init(
        id: UUID = UUID(),
        phoneNumber: String,
        callerLabel: String,
        callCategory: DemoCallCategory,
        status: DemoCallStatus,
        transcriptLines: [String],
        transferredToAI: Bool,
        startTime: Date
    ) {
        self.id = id
        self.phoneNumber = phoneNumber
        self.callerLabel = callerLabel
        self.callCategory = callCategory
        self.status = status
        self.transcriptLines = transcriptLines
        self.transferredToAI = transferredToAI
        self.startTime = startTime
    }

    func updating(
        status: DemoCallStatus? = nil,
        transferredToAI: Bool? = nil,
        transcriptLines: [String]? = nil
    ) -> DemoCallSession {
        DemoCallSession(
            id: id,
            phoneNumber: phoneNumber,
            callerLabel: callerLabel,
            callCategory: callCategory,
            status: status ?? self.status,
            transcriptLines: transcriptLines ?? self.transcriptLines,
            transferredToAI: transferredToAI ?? self.transferredToAI,
            startTime: startTime
        )
    }
}

enum VerificationState: String, Hashable {
    case verified
    case suspicious
    case unknown

    var title: String {
        switch self {
        case .verified:
            return "Verified Caller"
        case .suspicious:
            return "Suspicious Caller"
        case .unknown:
            return "Unknown Caller"
        }
    }
}

enum ThreatSeverity: String, Hashable {
    case low
    case medium
    case high
}

enum ProtectionConnectionState: String, Hashable, Codable {
    case prepared
    case connecting
    case live
    case playingDemoAudio
    case receivingAgentEvents
    case degraded

    var badgeText: String {
        switch self {
        case .prepared:
            return "Prepared"
        case .connecting:
            return "Connecting"
        case .live:
            return "Live"
        case .playingDemoAudio:
            return "Simulated Caller"
        case .receivingAgentEvents:
            return "Agent Events"
        case .degraded:
            return "Fallback"
        }
    }

    var fallbackStatusText: String {
        switch self {
        case .prepared:
            return "AI takeover prepared. Live call starts when protected connection opens."
        case .connecting:
            return "Connecting AI takeover to live conversation channel..."
        case .live:
            return "AI protection connected. Transcript analysis and scam monitoring in progress."
        case .playingDemoAudio:
            return "Running protected-call simulation with scripted caller turns."
        case .receivingAgentEvents:
            return "Receiving live AI events and transcript updates from active session."
        case .degraded:
            return "AI takeover started in fallback mode. Continuing protection and analysis."
        }
    }
}

struct ThreatTag: Hashable, Identifiable {
    let label: String
    let severity: ThreatSeverity

    var id: String {
        "\(label)-\(severity.rawValue)"
    }
}

struct VerificationResult: Hashable {
    let phoneNumber: String
    let state: VerificationState
    let explanation: String
    let threatTags: [ThreatTag]
    let confidence: Int?
    let sourceLabel: String?
    let riskLevel: String?
}

struct SessionEntity: Hashable, Identifiable {
    let key: String
    let value: String
    let confidence: Int

    var id: String {
        "\(key)-\(value)"
    }
}

struct ProtectionSession: Hashable {
    let sessionID: String?
    let callerNumber: String
    let callerLabel: String?
    let callCategory: DemoCallCategory?
    let aiAgentName: String
    let statusText: String
    let connectionState: ProtectionConnectionState
    let signedConversationURL: URL?
    let sourceCallSessionID: UUID?
    let sessionStartTime: Date
    let transcriptNotes: [String]
    let scamIndicators: [String]
    let extractedEntities: [SessionEntity]
    let businessIntelligenceSteps: [String]
}
