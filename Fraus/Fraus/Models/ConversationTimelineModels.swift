import Foundation

enum ConversationSpeaker: String, Hashable {
    case caller
    case frausAI

    var displayName: String {
        switch self {
        case .caller:
            return "Caller says"
        case .frausAI:
            return "Fraus AI says"
        }
    }
}

enum ConversationMessageStatus: String, Hashable {
    case partial
    case final
    case corrected
    case fallback
}

struct ConversationTimelineMessage: Identifiable, Hashable {
    let id: String
    let speaker: ConversationSpeaker
    let text: String
    let status: ConversationMessageStatus
    let order: Int
    let receivedAt: Date
}
