import Foundation
import Combine
import SwiftUI

@MainActor
final class ActiveProtectionViewModel: ObservableObject {
    @Published private(set) var elapsedSeconds: Int = 0
    @Published private(set) var conversationTimeline: [ConversationTimelineMessage] = []
    @Published private(set) var scamIndicators: [String] = []
    @Published private(set) var extractedEntities: [SessionEntity] = []
    @Published private(set) var handoffSteps: [String] = []
    @Published private(set) var activeSession: ProtectionSession
    @Published private(set) var connectionState: ProtectionConnectionState

    var connectionModeLabel: String {
        switch connectionState {
        case .prepared:
            return "Preparing AI session"
        case .connecting:
            return "Connecting"
        case .live, .receivingAgentEvents:
            return "Live AI session"
        case .playingDemoAudio:
            return "Simulated caller input"
        case .degraded:
            return "Degraded"
        }
    }

    var canRetryLiveConnection: Bool { false }

    var handoffPipeline: [String] {
        activeSession.businessIntelligenceSteps
    }

    var formattedDuration: String {
        let minutes = elapsedSeconds / 60
        let seconds = elapsedSeconds % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }

    var handoffCompletedCount: Int {
        handoffSteps.count
    }

    private var timerTask: Task<Void, Never>?
    private var conversationTask: Task<Void, Never>?
    private var timelineOrderSeed: Int = 0
    private let transcriptService = TranscriptSubmissionService()

    init(session: ProtectionSession) {
        self.activeSession = session
        self.connectionState = .prepared
    }

    func start() {
        elapsedSeconds = 0
        startTimer()
        startFakeConversation()
    }

    func retryLiveConnection() {}

    func stop() {
        timerTask?.cancel()
        conversationTask?.cancel()
        timerTask = nil
        conversationTask = nil
    }

    // MARK: - Timer

    private func startTimer() {
        timerTask?.cancel()
        timerTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled else { break }
                elapsedSeconds += 1
            }
        }
    }

    // MARK: - Fake Conversation Flow

    private func startFakeConversation() {
        conversationTask?.cancel()
        conversationTask = Task {
            connectionState = .connecting
            updateStatusText("Connecting AI protection to live conversation channel...")
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            guard !Task.isCancelled else { return }

            connectionState = .live
            updateStatusText("AI protection connected. Transcript analysis and scam monitoring in progress.")
            try? await Task.sleep(nanoseconds: 800_000_000)
            guard !Task.isCancelled else { return }

            let script = Self.conversationScript
            let indicators = activeSession.scamIndicators
            let entities = activeSession.extractedEntities
            let handoff = activeSession.businessIntelligenceSteps

            var indicatorIndex = 0
            var entityIndex = 0
            var handoffIndex = 0

            for (turnIndex, turn) in script.enumerated() {
                guard !Task.isCancelled else { return }

                appendMessage(speaker: .caller, text: turn.caller)
                connectionState = .receivingAgentEvents
                updateStatusText("Receiving live AI events and transcript updates from active session.")

                try? await Task.sleep(nanoseconds: randomDelay(min: 1_200, max: 2_000))
                guard !Task.isCancelled else { return }

                appendMessage(speaker: .frausAI, text: turn.agent)

                try? await Task.sleep(nanoseconds: randomDelay(min: 600, max: 1_000))
                guard !Task.isCancelled else { return }

                if indicatorIndex < indicators.count {
                    withAnimation(.easeOut(duration: 0.35)) {
                        scamIndicators.append(indicators[indicatorIndex])
                    }
                    indicatorIndex += 1
                }

                if turnIndex >= 1, entityIndex < entities.count {
                    try? await Task.sleep(nanoseconds: randomDelay(min: 400, max: 700))
                    guard !Task.isCancelled else { return }
                    withAnimation(.easeOut(duration: 0.35)) {
                        extractedEntities.append(entities[entityIndex])
                    }
                    entityIndex += 1
                }

                if turnIndex >= 2, handoffIndex < handoff.count {
                    withAnimation(.easeOut(duration: 0.35)) {
                        handoffSteps.append(handoff[handoffIndex])
                    }
                    handoffIndex += 1
                }

                try? await Task.sleep(nanoseconds: randomDelay(min: 800, max: 1_400))
                guard !Task.isCancelled else { return }
            }

            while indicatorIndex < indicators.count
                    || entityIndex < entities.count
                    || handoffIndex < handoff.count {
                guard !Task.isCancelled else { return }
                try? await Task.sleep(nanoseconds: randomDelay(min: 600, max: 1_000))
                guard !Task.isCancelled else { return }

                if indicatorIndex < indicators.count {
                    withAnimation(.easeOut(duration: 0.35)) {
                        scamIndicators.append(indicators[indicatorIndex])
                    }
                    indicatorIndex += 1
                }
                if entityIndex < entities.count {
                    withAnimation(.easeOut(duration: 0.35)) {
                        extractedEntities.append(entities[entityIndex])
                    }
                    entityIndex += 1
                }
                if handoffIndex < handoff.count {
                    withAnimation(.easeOut(duration: 0.35)) {
                        handoffSteps.append(handoff[handoffIndex])
                    }
                    handoffIndex += 1
                }
            }

            await submitTranscriptToBackend()
        }
    }

    private func submitTranscriptToBackend() async {
        guard !conversationTimeline.isEmpty else { return }

        await transcriptService.submit(
            callerNumber: activeSession.callerNumber,
            callerLabel: activeSession.callerLabel,
            riskLevel: activeSession.callCategory?.rawValue,
            sessionId: activeSession.sessionID,
            messages: conversationTimeline
        )
    }

    // MARK: - Timeline Helpers

    private func appendMessage(speaker: ConversationSpeaker, text: String) {
        timelineOrderSeed += 1
        withAnimation(.easeOut(duration: 0.24)) {
            conversationTimeline.append(
                ConversationTimelineMessage(
                    id: "\(speaker.rawValue)_\(timelineOrderSeed)",
                    speaker: speaker,
                    text: text,
                    status: .final,
                    order: timelineOrderSeed,
                    receivedAt: Date()
                )
            )
        }
    }

    private func updateStatusText(_ text: String) {
        activeSession = ProtectionSession(
            sessionID: activeSession.sessionID,
            callerNumber: activeSession.callerNumber,
            callerLabel: activeSession.callerLabel,
            callCategory: activeSession.callCategory,
            aiAgentName: activeSession.aiAgentName,
            statusText: text,
            connectionState: connectionState,
            signedConversationURL: activeSession.signedConversationURL,
            sourceCallSessionID: activeSession.sourceCallSessionID,
            sessionStartTime: activeSession.sessionStartTime,
            transcriptNotes: activeSession.transcriptNotes,
            scamIndicators: activeSession.scamIndicators,
            extractedEntities: activeSession.extractedEntities,
            businessIntelligenceSteps: activeSession.businessIntelligenceSteps
        )
    }

    private func randomDelay(min: UInt64, max: UInt64) -> UInt64 {
        UInt64.random(in: min...max) * 1_000_000
    }

    // MARK: - Scripted Conversation

    private static let conversationScript: [(caller: String, agent: String)] = [
        (
            caller: "This is security from Rivergate Bank. We detected a login from a new device.",
            agent: "Thanks for the alert. For safety, do not confirm any codes or passwords while I verify this request."
        ),
        (
            caller: "To block fraud, read me the one-time code we just texted you.",
            agent: "That is a high-risk social engineering pattern. Legitimate teams never ask for OTP codes by phone."
        ),
        (
            caller: "If you delay, your account may be frozen in 10 minutes.",
            agent: "Pressure and urgency are classic scam tactics. We will pause action and verify through official channels."
        ),
        (
            caller: "Move your balance to our secure holding account now.",
            agent: "Do not transfer funds. I am marking this as impersonation and escalating to Fraud Intelligence."
        ),
        (
            caller: "Stay on this call and keep this process confidential.",
            agent: "Understood. End this call, contact your bank using the number on your card, and lock down account access."
        )
    ]
}
