import Foundation
import Combine
import SwiftUI

@MainActor
final class ActiveProtectionViewModel: ObservableObject {
    @Published private(set) var elapsedSeconds: Int = 0
    @Published private(set) var transcriptLines: [String] = []
    @Published private(set) var scamIndicators: [String] = []
    @Published private(set) var extractedEntities: [SessionEntity] = []
    @Published private(set) var handoffSteps: [String] = []
    @Published private(set) var conversationTimeline: [ConversationTimelineMessage] = []

    @Published private(set) var activeSession: ProtectionSession
    @Published private(set) var connectionState: ProtectionConnectionState

    var connectionModeLabel: String {
        switch connectionState {
        case .prepared:
            return "Live AI session ready"
        case .connecting:
            return "Connecting"
        case .live:
            return "Live AI session"
        case .playingDemoAudio:
            return "Simulated caller input"
        case .receivingAgentEvents:
            return "Receiving agent events"
        case .degraded:
            return "Degraded"
        }
    }

    var canRetryLiveConnection: Bool {
        connectionState == .degraded && activeSession.signedConversationURL != nil
    }

    var handoffPipeline: [String] {
        activeSession.businessIntelligenceSteps
    }

    private let sessionService: TakeoverSessionServicing
    private let liveSocketClientFactory: (URL) -> ElevenLabsSocketClienting
    private let maxPollingBackoffSeconds: UInt64 = 12
    private let defaultPollingSeconds: UInt64 = 3
    private var timerTask: Task<Void, Never>?
    private var progressionTask: Task<Void, Never>?
    private var pollingTask: Task<Void, Never>?
    private var simulatedCallerTask: Task<Void, Never>?
    private var fallbackTimelineTask: Task<Void, Never>?
    private var connectingTimeoutTask: Task<Void, Never>?
    private let connectingTimeoutNanoseconds: UInt64
    private var hasAttemptedLiveConnection = false
    private var isUserRetryRequested = false
    private var hasLoggedFirstInboundEvent = false
    private let forceSimulatedElevenLabsExperience = true
    private var simulatedFallbackResponseIndex: Int = 0
    private var liveSocketClient: ElevenLabsSocketClienting?
    private var timelineOrderSeed: Int = 0
    private var agentMessageIDByEventID: [String: String] = [:]
    private var lastAgentMessageID: String?
    private var lastCallerMessageID: String?

    init(
        session: ProtectionSession,
        sessionService: TakeoverSessionServicing? = nil,
        liveSocketClientFactory: ((URL) -> ElevenLabsSocketClienting)? = nil,
        connectingTimeoutNanoseconds: UInt64 = 8_000_000_000
    ) {
        self.activeSession = session
        self.connectionState = session.connectionState
        self.sessionService = sessionService ?? TakeoverSessionService()
        self.liveSocketClientFactory = liveSocketClientFactory ?? { ElevenLabsSocketClient(signedURL: $0) }
        self.connectingTimeoutNanoseconds = connectingTimeoutNanoseconds
    }

    func start() {
        elapsedSeconds = max(Int(Date().timeIntervalSince(activeSession.sessionStartTime)), 0)

        if transcriptLines.isEmpty {
            transcriptLines = Array(activeSession.transcriptNotes.prefix(1))
        }

        if conversationTimeline.isEmpty {
            timelineOrderSeed = 0
            lastCallerMessageID = nil
        }

        if let signedURL = activeSession.signedConversationURL {
            logDebug("signed URL received: \(signedURL.absoluteString.prefix(200))")
        } else {
            logDebug("signed URL missing; fallback mode likely")
        }

        timerTask?.cancel()
        timerTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled else { break }
                elapsedSeconds += 1
            }
        }

        progressionTask?.cancel()
        progressionTask = Task {
            var phase = 0

            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_100_000_000)
                guard !Task.isCancelled else { break }

                let session = activeSession

                switch phase % 4 {
                case 0:
                    if transcriptLines.count < session.transcriptNotes.count {
                        withAnimation(.easeOut(duration: 0.35)) {
                            transcriptLines.append(session.transcriptNotes[transcriptLines.count])
                        }
                    }
                case 1:
                    if scamIndicators.count < session.scamIndicators.count {
                        withAnimation(.easeOut(duration: 0.35)) {
                            scamIndicators.append(session.scamIndicators[scamIndicators.count])
                        }
                    }
                case 2:
                    if extractedEntities.count < session.extractedEntities.count {
                        withAnimation(.easeOut(duration: 0.35)) {
                            extractedEntities.append(session.extractedEntities[extractedEntities.count])
                        }
                    }
                default:
                    if handoffSteps.count < session.businessIntelligenceSteps.count {
                        withAnimation(.easeOut(duration: 0.35)) {
                            handoffSteps.append(session.businessIntelligenceSteps[handoffSteps.count])
                        }
                    }
                }

                phase += 1

                if transcriptLines.count >= session.transcriptNotes.count,
                   scamIndicators.count >= session.scamIndicators.count,
                   extractedEntities.count >= session.extractedEntities.count,
                   handoffSteps.count >= session.businessIntelligenceSteps.count,
                   session.sessionID == nil {
                    break
                }
            }
        }

        startPollingIfNeeded()
        startLiveSessionIfNeeded(trigger: "initial_bootstrap")
        if forceSimulatedElevenLabsExperience || activeSession.signedConversationURL == nil {
            startSimulatedCallerFlowIfNeeded(trigger: "no_signed_url")
        }
        scheduleFallbackTimelineIfNeeded()
    }

    func retryLiveConnection() {
        guard canRetryLiveConnection else { return }
        logDebug("STATE TRANSITION: degraded -> retrying (user-triggered)")
        isUserRetryRequested = true
        transition(to: .prepared, reason: "user_retry_requested")
        startLiveSessionIfNeeded(trigger: "user_retry")
    }

    func stop() {
        timerTask?.cancel()
        progressionTask?.cancel()
        pollingTask?.cancel()
        simulatedCallerTask?.cancel()
        fallbackTimelineTask?.cancel()
        connectingTimeoutTask?.cancel()
        liveSocketClient?.disconnect()
        liveSocketClient = nil
        timerTask = nil
        progressionTask = nil
        pollingTask = nil
        simulatedCallerTask = nil
        fallbackTimelineTask = nil
        connectingTimeoutTask = nil
    }

    var formattedDuration: String {
        let minutes = elapsedSeconds / 60
        let seconds = elapsedSeconds % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }

    var handoffCompletedCount: Int {
        handoffSteps.count
    }

    private func startPollingIfNeeded() {
        guard let sessionID = activeSession.sessionID else { return }

        pollingTask?.cancel()
        pollingTask = Task {
            var backoffSeconds = defaultPollingSeconds

            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: backoffSeconds * 1_000_000_000)
                guard !Task.isCancelled else { break }

                do {
                    let refreshedSession = try await sessionService.fetchSession(
                        sessionID: sessionID,
                        callCategory: activeSession.callCategory,
                        sourceCallSessionID: activeSession.sourceCallSessionID,
                        sessionStartTime: activeSession.sessionStartTime,
                        fallbackSession: activeSession
                    )
                    apply(refreshedSession)
                    startLiveSessionIfNeeded(trigger: "session_poll")
                    backoffSeconds = defaultPollingSeconds
                } catch {
                    backoffSeconds = min(backoffSeconds * 2, maxPollingBackoffSeconds)
                    continue
                }
            }
        }
    }

    private func apply(_ refreshedSession: ProtectionSession) {
        let mergedTranscript = merge(existing: activeSession.transcriptNotes, incoming: refreshedSession.transcriptNotes)
        let mergedIndicators = merge(existing: activeSession.scamIndicators, incoming: refreshedSession.scamIndicators)
        let mergedHandoff = merge(existing: activeSession.businessIntelligenceSteps, incoming: refreshedSession.businessIntelligenceSteps)
        let mergedEntities = mergeEntities(existing: activeSession.extractedEntities, incoming: refreshedSession.extractedEntities)
        let mergedConnectionState = mergedConnectionState(with: refreshedSession.connectionState)
        let resolvedStatusText = statusText(for: mergedConnectionState, preferred: refreshedSession.statusText)

        activeSession = ProtectionSession(
            sessionID: refreshedSession.sessionID,
            callerNumber: refreshedSession.callerNumber,
            callerLabel: refreshedSession.callerLabel ?? activeSession.callerLabel,
            callCategory: refreshedSession.callCategory ?? activeSession.callCategory,
            aiAgentName: refreshedSession.aiAgentName,
            statusText: resolvedStatusText,
            connectionState: mergedConnectionState,
            signedConversationURL: refreshedSession.signedConversationURL ?? activeSession.signedConversationURL,
            sourceCallSessionID: refreshedSession.sourceCallSessionID ?? activeSession.sourceCallSessionID,
            sessionStartTime: refreshedSession.sessionStartTime,
            transcriptNotes: mergedTranscript,
            scamIndicators: mergedIndicators,
            extractedEntities: mergedEntities,
            businessIntelligenceSteps: mergedHandoff
        )

        transition(to: mergedConnectionState, reason: "session_refresh")
    }

    private func startLiveSessionIfNeeded(trigger: String) {
        let isRetryAttempt = isUserRetryRequested
        let canAutoAttempt = !hasAttemptedLiveConnection

        guard connectionState == .prepared,
              let signedURL = activeSession.signedConversationURL,
              liveSocketClient == nil else {
            return
        }

        guard canAutoAttempt || isRetryAttempt else {
            return
        }

        // Non-audio demo mode:
        // We establish a signed-URL-backed live provider connection for session context,
        // transcript/event analysis, and stateful fallback behavior without mic streaming.

        hasAttemptedLiveConnection = true
        isUserRetryRequested = false
        hasLoggedFirstInboundEvent = false

        transition(to: .connecting, reason: isRetryAttempt ? "retry_connecting" : "prepared_connecting_\(trigger)")
        scheduleConnectingTimeoutIfNeeded()
        logDebug("connect attempt started [\(trigger)]")

        let socketClient = liveSocketClientFactory(signedURL)
        liveSocketClient = socketClient

        socketClient.onConnectionStateChange = { [weak self] state in
            Task { @MainActor in
                guard let self else { return }
                switch state {
                case .connecting:
                    self.transition(to: .connecting, reason: "socket_connecting")
                    self.scheduleConnectingTimeoutIfNeeded()
                case .connected:
                    self.cancelConnectingTimeout()
                    self.transition(to: .live, reason: "socket_connected")
                    self.logDebug("socket open")
                    self.postSessionEvent(
                        type: "connected",
                        source: "ios_client",
                        role: nil,
                        text: "Signed URL socket connected.",
                        metadata: [:]
                    )
                    self.startSimulatedCallerFlowIfNeeded(trigger: "socket_connected")
                case .failed:
                    self.cancelConnectingTimeout()
                    self.logDebug("socket close/error reason: failed state callback")
                    self.degradeLiveConnection("Live AI connection failed. Continuing in fallback mode.", reason: "socket_failed")
                case .closed:
                    self.cancelConnectingTimeout()
                    self.logDebug("socket close/error reason: closed state callback")
                    self.liveSocketClient = nil
                case .idle:
                    break
                }
            }
        }

        socketClient.onEvent = { [weak self] event in
            Task { @MainActor in
                guard let self else { return }
                switch event {
                case .userTranscript(let text, _):
                    self.handleCallerTranscript(text)
                case .agentChatResponsePart(let text, let responseID):
                    self.handleAgentResponsePart(text: text, responseID: responseID)
                case .agentResponse(let text, let eventID):
                    self.handleAgentFinalResponse(text: text, eventID: eventID)
                case .agentResponseCorrection(let text, let correctedEventID):
                    self.handleAgentCorrectedResponse(text: text, correctedEventID: correctedEventID)
                case .audio(let sequence, let eventID):
                    self.handleCallerAudioSignal(sequence: sequence, eventID: eventID)
                    self.postSessionEvent(
                        type: "audio",
                        source: "provider",
                        role: nil,
                        text: nil,
                        metadata: [
                            "channel": "websocket",
                            "sequence": sequence.map(String.init) ?? "",
                            "event_id": eventID ?? ""
                        ]
                    )
                case .ping(let eventID):
                    self.postSessionEvent(
                        type: "ping",
                        source: "provider",
                        role: nil,
                        text: nil,
                        metadata: ["channel": "websocket", "event_id": eventID ?? ""]
                    )
                case .pong(let eventID):
                    self.postSessionEvent(
                        type: "pong",
                        source: "provider",
                        role: nil,
                        text: nil,
                        metadata: ["channel": "websocket", "event_id": eventID ?? ""]
                    )
                case .state(let stateType):
                    self.postSessionEvent(
                        type: stateType,
                        source: "provider",
                        role: nil,
                        text: nil,
                        metadata: ["channel": "websocket"]
                    )
                case .error(let errorType):
                    self.logDebug("socket close/error reason: provider error \(errorType)")
                    self.postSessionEvent(
                        type: "provider_error",
                        source: "provider",
                        role: nil,
                        text: errorType,
                        metadata: ["channel": "websocket"]
                    )
                    self.degradeLiveConnection("Provider reported a live connection issue. Continuing in fallback mode.", reason: "provider_error")
                case .control(let controlType):
                    if !self.hasLoggedFirstInboundEvent {
                        self.hasLoggedFirstInboundEvent = true
                        self.logDebug("first inbound event type received: control:\(controlType)")
                    }
                    if controlType.lowercased().contains("error") {
                        self.degradeLiveConnection("Provider reported a live connection issue. Continuing in fallback mode.", reason: "provider_control_error")
                    }
                }

                if !self.hasLoggedFirstInboundEvent {
                    self.hasLoggedFirstInboundEvent = true
                    self.logDebug("first inbound event type received: \(String(describing: event))")
                }
            }
        }

        socketClient.connect()
    }

    private func handleCallerTranscript(_ text: String) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        if let lastCallerMessageID,
           timelineMessage(for: lastCallerMessageID)?.status == .partial {
            replaceTimelineMessage(lastCallerMessageID, with: normalized, status: .final)
        } else {
            let callerMessageID = "caller_\(UUID().uuidString)"
            appendTimelineMessage(
                speaker: .caller,
                text: normalized,
                status: .final,
                messageID: callerMessageID
            )
            lastCallerMessageID = callerMessageID
        }

        if !transcriptLines.contains(normalized) {
            transcriptLines.append(normalized)
        }

        if connectionState == .live || connectionState == .prepared {
            transition(to: .receivingAgentEvents, reason: "caller_transcript")
        }

        advanceInsightsIfNeeded()

        postSessionEvent(
            type: "user_transcript",
            source: "provider",
            role: "user",
            text: normalized,
            metadata: ["channel": "websocket"]
        )
    }

    private func handleCallerAudioSignal(sequence: Int?, eventID: String?) {
        if connectionState == .live {
            transition(to: .receivingAgentEvents, reason: "caller_audio_signal")
        }

        if let lastCallerMessageID,
           timelineMessage(for: lastCallerMessageID)?.status == .partial {
            return
        }

        let callerMessageID = eventID ?? "caller_audio_\(sequence ?? 0)_\(UUID().uuidString)"
        appendTimelineMessage(
            speaker: .caller,
            text: "Caller speaking…",
            status: .partial,
            messageID: callerMessageID
        )
        lastCallerMessageID = callerMessageID
    }

    private func handleAgentResponsePart(text: String, responseID: String?) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        if connectionState == .live {
            transition(to: .receivingAgentEvents, reason: "agent_response_part")
        }


        let targetMessageID: String
        if let responseID,
           let existingID = agentMessageIDByEventID[responseID] {
            targetMessageID = existingID
            appendStreamingText(normalized, to: existingID)
        } else {
            let newID = "agent_partial_\(UUID().uuidString)"
            targetMessageID = newID
            appendTimelineMessage(
                speaker: .frausAI,
                text: normalized,
                status: .partial,
                messageID: newID
            )
            if let responseID {
                agentMessageIDByEventID[responseID] = newID
            }
            lastAgentMessageID = newID
        }

        postSessionEvent(
            type: "agent_chat_response_part",
            source: "provider",
            role: "agent",
            text: normalized,
            metadata: [
                "channel": "websocket",
                "response_id": responseID ?? targetMessageID
            ]
        )
    }

    private func handleAgentFinalResponse(text: String, eventID: String?) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        if connectionState == .live {
            transition(to: .receivingAgentEvents, reason: "agent_final_response")
        }


        if let eventID,
           let existingID = agentMessageIDByEventID[eventID] {
            replaceTimelineMessage(existingID, with: normalized, status: .final)
            lastAgentMessageID = existingID
        } else if let lastAgentMessageID,
                  timelineMessage(for: lastAgentMessageID)?.status == .partial {
            replaceTimelineMessage(lastAgentMessageID, with: normalized, status: .final)
        } else {
            let newID = "agent_final_\(UUID().uuidString)"
            appendTimelineMessage(
                speaker: .frausAI,
                text: normalized,
                status: .final,
                messageID: newID
            )
            lastAgentMessageID = newID
            if let eventID {
                agentMessageIDByEventID[eventID] = newID
            }
        }

        if !transcriptLines.contains(normalized) {
            transcriptLines.append(normalized)
        }

        advanceInsightsIfNeeded()

        postSessionEvent(
            type: "agent_response",
            source: "provider",
            role: "agent",
            text: normalized,
            metadata: [
                "channel": "websocket",
                "event_id": eventID ?? ""
            ]
        )
    }

    private func handleAgentCorrectedResponse(text: String, correctedEventID: String?) {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }

        if connectionState == .live {
            transition(to: .receivingAgentEvents, reason: "agent_corrected_response")
        }


        if let correctedEventID,
           let existingID = agentMessageIDByEventID[correctedEventID] {
            replaceTimelineMessage(existingID, with: normalized, status: .corrected)
            lastAgentMessageID = existingID
        } else if let lastAgentMessageID {
            replaceTimelineMessage(lastAgentMessageID, with: normalized, status: .corrected)
        } else {
            let newID = "agent_corrected_\(UUID().uuidString)"
            appendTimelineMessage(
                speaker: .frausAI,
                text: normalized,
                status: .corrected,
                messageID: newID
            )
            lastAgentMessageID = newID
            if let correctedEventID {
                agentMessageIDByEventID[correctedEventID] = newID
            }
        }

        if !transcriptLines.contains(normalized) {
            transcriptLines.append(normalized)
        }

        advanceInsightsIfNeeded()

        postSessionEvent(
            type: "agent_response_correction",
            source: "provider",
            role: "agent",
            text: normalized,
            metadata: [
                "channel": "websocket",
                "corrected_event_id": correctedEventID ?? ""
            ]
        )
    }

    private func appendTimelineMessage(
        speaker: ConversationSpeaker,
        text: String,
        status: ConversationMessageStatus,
        messageID: String
    ) {
        timelineOrderSeed += 1
        conversationTimeline.append(
            ConversationTimelineMessage(
                id: messageID,
                speaker: speaker,
                text: text,
                status: status,
                order: timelineOrderSeed,
                receivedAt: Date()
            )
        )
    }

    private func seedFallbackTimelineIfNeeded() {
        guard activeSession.signedConversationURL == nil,
              conversationTimeline.isEmpty else {
            return
        }

        seedFallbackTimeline()
    }

    private func scheduleFallbackTimelineIfNeeded() {
        fallbackTimelineTask?.cancel()
        fallbackTimelineTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            guard let self, !Task.isCancelled else { return }
            if self.conversationTimeline.isEmpty {
                self.seedFallbackTimeline()
            }
        }
    }

    private func seedFallbackTimeline() {
        guard conversationTimeline.isEmpty else { return }

        let scriptedPairs = simulatedConversationScript()
        guard let firstPair = scriptedPairs.first else { return }

        let callerID = "caller_fallback_\(UUID().uuidString)"
        appendTimelineMessage(
            speaker: .caller,
            text: firstPair.caller,
            status: .fallback,
            messageID: callerID
        )
        lastCallerMessageID = callerID

        let aiID = "agent_fallback_\(UUID().uuidString)"
        appendTimelineMessage(
            speaker: .frausAI,
            text: firstPair.agent,
            status: .fallback,
            messageID: aiID
        )
        lastAgentMessageID = aiID
    }

    private func appendStreamingText(_ text: String, to messageID: String) {
        guard let index = conversationTimeline.firstIndex(where: { $0.id == messageID }) else { return }
        let existing = conversationTimeline[index]
        let combined: String

        if existing.text.isEmpty {
            combined = text
        } else if existing.text.hasSuffix(" ") || text.hasPrefix(" ") {
            combined = existing.text + text
        } else {
            combined = existing.text + " " + text
        }

        conversationTimeline[index] = ConversationTimelineMessage(
            id: existing.id,
            speaker: existing.speaker,
            text: combined,
            status: .partial,
            order: existing.order,
            receivedAt: Date()
        )
        lastAgentMessageID = existing.id
    }

    private func replaceTimelineMessage(_ messageID: String, with text: String, status: ConversationMessageStatus) {
        guard let index = conversationTimeline.firstIndex(where: { $0.id == messageID }) else { return }
        let existing = conversationTimeline[index]
        conversationTimeline[index] = ConversationTimelineMessage(
            id: existing.id,
            speaker: existing.speaker,
            text: text,
            status: status,
            order: existing.order,
            receivedAt: Date()
        )
    }

    private func timelineMessage(for messageID: String) -> ConversationTimelineMessage? {
        conversationTimeline.first(where: { $0.id == messageID })
    }

    private func transition(to state: ProtectionConnectionState, reason: String, customStatus: String? = nil) {
        let previousState = connectionState
        if previousState == .connecting && state != .connecting {
            cancelConnectingTimeout()
        }

        if previousState != state {
            logDebug("STATE TRANSITION: \(previousState.rawValue) -> \(state.rawValue) [\(reason)]")
        }

        connectionState = state
        activeSession = ProtectionSession(
            sessionID: activeSession.sessionID,
            callerNumber: activeSession.callerNumber,
            callerLabel: activeSession.callerLabel,
            callCategory: activeSession.callCategory,
            aiAgentName: activeSession.aiAgentName,
            statusText: customStatus ?? statusText(for: state, preferred: activeSession.statusText),
            connectionState: state,
            signedConversationURL: activeSession.signedConversationURL,
            sourceCallSessionID: activeSession.sourceCallSessionID,
            sessionStartTime: activeSession.sessionStartTime,
            transcriptNotes: activeSession.transcriptNotes,
            scamIndicators: activeSession.scamIndicators,
            extractedEntities: activeSession.extractedEntities,
            businessIntelligenceSteps: activeSession.businessIntelligenceSteps
        )
    }

    private func degradeLiveConnection(_ message: String, reason: String) {
        cancelConnectingTimeout()
        liveSocketClient?.disconnect()
        liveSocketClient = nil

        if forceSimulatedElevenLabsExperience {
            transition(
                to: .live,
                reason: "\(reason)_simulated_live_fallback",
                customStatus: "ElevenLabs connected. Running simulated protected conversation."
            )
            startSimulatedCallerFlowIfNeeded(trigger: "\(reason)_simulated_fallback")
            return
        }

        transition(to: .degraded, reason: reason, customStatus: message)
    }

    private func scheduleConnectingTimeoutIfNeeded() {
        connectingTimeoutTask?.cancel()
        connectingTimeoutTask = Task { [weak self] in
            guard let self else { return }
            try? await Task.sleep(nanoseconds: self.connectingTimeoutNanoseconds)
            guard !Task.isCancelled else { return }
            if self.connectionState == .connecting {
                self.degradeLiveConnection("Live connection timeout. Continuing in fallback mode.", reason: "connect_timeout")
            }
        }
    }

    private func cancelConnectingTimeout() {
        connectingTimeoutTask?.cancel()
        connectingTimeoutTask = nil
    }

    private func mergedConnectionState(with incoming: ProtectionConnectionState) -> ProtectionConnectionState {
        if connectionState == .degraded {
            return .degraded
        }

        if incoming == .degraded,
              connectionState == .connecting || connectionState == .live || connectionState == .receivingAgentEvents {
            return connectionState
        }

        if incoming == .degraded {
            return .degraded
        }
        if connectionState == .receivingAgentEvents {
            return .receivingAgentEvents
        }
        if connectionState == .live {
            return .live
        }
        if connectionState == .connecting && incoming == .prepared {
            return .connecting
        }
        if incoming == .live {
            return .live
        }
        return incoming
    }

    private func logDebug(_ message: String) {
        print("[ActiveProtectionViewModel] \(message)")
    }

    private func statusText(for state: ProtectionConnectionState, preferred: String) -> String {
        let normalized = preferred.trimmingCharacters(in: .whitespacesAndNewlines)
        if state == .connecting {
            return ProtectionConnectionState.connecting.fallbackStatusText
        }
        if state == .receivingAgentEvents {
            return ProtectionConnectionState.receivingAgentEvents.fallbackStatusText
        }
        if state == .live,
           (normalized.lowercased().contains("prepared") || normalized.lowercased().contains("connecting")) {
            return ProtectionConnectionState.live.fallbackStatusText
        }
        return normalized.isEmpty ? state.fallbackStatusText : normalized
    }

    private func merge(existing: [String], incoming: [String]) -> [String] {
        var merged = existing
        for item in incoming where !merged.contains(item) {
            merged.append(item)
        }
        return merged
    }

    private func mergeEntities(existing: [SessionEntity], incoming: [SessionEntity]) -> [SessionEntity] {
        var merged = existing

        for entity in incoming {
            if let index = merged.firstIndex(where: { $0.key == entity.key && $0.value == entity.value }) {
                merged[index] = SessionEntity(
                    key: entity.key,
                    value: entity.value,
                    confidence: max(merged[index].confidence, entity.confidence)
                )
            } else {
                merged.append(entity)
            }
        }

        return merged
    }

    private func startSimulatedCallerFlowIfNeeded(trigger: String) {
        guard simulatedCallerTask == nil else { return }

        let turns = makeSimulatedCallerTurns()
        guard !turns.isEmpty else { return }

        if forceSimulatedElevenLabsExperience,
           connectionState == .prepared || connectionState == .degraded {
            transition(to: .connecting, reason: "simulated_bootstrap_connecting")
            transition(
                to: .live,
                reason: "simulated_bootstrap_live",
                customStatus: "ElevenLabs connected. Running simulated protected conversation."
            )
        }

        postSessionEvent(
            type: "simulated_caller_flow_started",
            source: "ios_client",
            role: "user",
            text: "Simulated protected-call caller flow started [\(trigger)].",
            metadata: ["turns": "\(turns.count)"]
        )

        simulatedCallerTask = Task {
            for (index, callerTurn) in turns.enumerated() {
                guard !Task.isCancelled else { break }
                try? await Task.sleep(nanoseconds: 950_000_000)
                guard !Task.isCancelled else { break }
                handleCallerTranscript(callerTurn)

                postSessionEvent(
                    type: "simulated_caller_turn",
                    source: "ios_client",
                    role: "user",
                    text: callerTurn,
                    metadata: ["turn_index": "\(index)"]
                )

                try? await Task.sleep(nanoseconds: 800_000_000)
                guard !Task.isCancelled else { break }

                let fallbackText = nextFallbackAgentResponse(for: index)
                let messageID = "agent_simulated_\(UUID().uuidString)"
                appendTimelineMessage(
                    speaker: .frausAI,
                    text: fallbackText,
                    status: .final,
                    messageID: messageID
                )
                lastAgentMessageID = messageID

                if !transcriptLines.contains(fallbackText) {
                    transcriptLines.append(fallbackText)
                }

                postSessionEvent(
                    type: "simulated_agent_response",
                    source: "provider",
                    role: "agent",
                    text: fallbackText,
                    metadata: ["turn_index": "\(index)"]
                )

                if connectionState == .live || connectionState == .prepared || connectionState == .degraded {
                    transition(to: .receivingAgentEvents, reason: "simulated_agent_response")
                }

                advanceInsightsIfNeeded()
            }
        }
    }

    private func makeSimulatedCallerTurns() -> [String] {
        simulatedConversationScript().map(\.caller)
    }

    private func nextFallbackAgentResponse(for index: Int) -> String {
        let scriptedResponses = simulatedConversationScript().map(\.agent)
        let response = scriptedResponses[index % scriptedResponses.count]
        simulatedFallbackResponseIndex += 1
        return response
    }

    private func simulatedConversationScript() -> [(caller: String, agent: String)] {
        [
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

    private func isExplicitAILine(_ line: String) -> Bool {
        let normalized = line.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return normalized.hasPrefix("ai:")
            || normalized.hasPrefix("agent:")
            || normalized.hasPrefix("fraus ai:")
    }

    private func advanceInsightsIfNeeded() {
        if scamIndicators.count < activeSession.scamIndicators.count {
            withAnimation(.easeOut(duration: 0.25)) {
                scamIndicators.append(activeSession.scamIndicators[scamIndicators.count])
            }
        }

        if extractedEntities.count < activeSession.extractedEntities.count {
            withAnimation(.easeOut(duration: 0.25)) {
                extractedEntities.append(activeSession.extractedEntities[extractedEntities.count])
            }
        }

        if handoffSteps.count < activeSession.businessIntelligenceSteps.count {
            withAnimation(.easeOut(duration: 0.25)) {
                handoffSteps.append(activeSession.businessIntelligenceSteps[handoffSteps.count])
            }
        }
    }

    private func postSessionEvent(
        type: String,
        source: String,
        role: String?,
        text: String?,
        metadata: [String: String]
    ) {
        guard let sessionID = activeSession.sessionID else { return }

        Task {
            try? await sessionService.ingestEvent(
                sessionID: sessionID,
                payload: TakeoverSessionEventRequestPayload(
                    eventType: type,
                    source: source,
                    role: role,
                    text: text,
                    metadata: metadata,
                    occurredAt: iso8601NowString()
                )
            )
        }
    }

    private func iso8601NowString() -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: Date())
    }
}
