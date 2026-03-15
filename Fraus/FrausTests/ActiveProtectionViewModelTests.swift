import XCTest
import Combine
@testable import Fraus

@MainActor
final class ActiveProtectionViewModelTests: XCTestCase {
    func testNoReconnectLoopAfterTimeoutAndDegradedStability() async throws {
        let sessionService = MockTakeoverSessionService()
        let socket = MockSocketClient(scenarios: [.stallConnecting])

        let session = ProtectionSession(
            sessionID: "fraus_timeout_session",
            callerNumber: "+19005550199",
            callerLabel: "Possible Bank Impersonation",
            callCategory: .scam,
            aiAgentName: "Fraus Sentinel v1",
            statusText: ProtectionConnectionState.prepared.fallbackStatusText,
            connectionState: .prepared,
            signedConversationURL: URL(string: "wss://example.com/signed")!,
            sourceCallSessionID: UUID(),
            sessionStartTime: Date(),
            transcriptNotes: ["Caller: urgent account access required"],
            scamIndicators: [],
            extractedEntities: [],
            businessIntelligenceSteps: []
        )

        let viewModel = ActiveProtectionViewModel(
            session: session,
            sessionService: sessionService,
            liveSocketClientFactory: { _ in socket },
            connectingTimeoutNanoseconds: 180_000_000
        )

        viewModel.start()
        try? await Task.sleep(nanoseconds: 700_000_000)

        XCTAssertEqual(socket.connectCallCount, 1)
        XCTAssertEqual(viewModel.connectionState, .degraded)

        try? await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(socket.connectCallCount, 1)
        XCTAssertEqual(viewModel.connectionState, .degraded)

        viewModel.stop()
    }

    func testExplicitRetryCreatesOneNewAttempt() async throws {
        let sessionService = MockTakeoverSessionService()
        let socket = MockSocketClient(scenarios: [.stallConnecting, .connectSuccess(eventsAfterConnect: [])])

        let session = ProtectionSession(
            sessionID: "fraus_retry_session",
            callerNumber: "+19005550199",
            callerLabel: "Possible Bank Impersonation",
            callCategory: .scam,
            aiAgentName: "Fraus Sentinel v1",
            statusText: ProtectionConnectionState.prepared.fallbackStatusText,
            connectionState: .prepared,
            signedConversationURL: URL(string: "wss://example.com/signed")!,
            sourceCallSessionID: UUID(),
            sessionStartTime: Date(),
            transcriptNotes: ["Caller: urgent account access required"],
            scamIndicators: [],
            extractedEntities: [],
            businessIntelligenceSteps: []
        )

        let viewModel = ActiveProtectionViewModel(
            session: session,
            sessionService: sessionService,
            liveSocketClientFactory: { _ in socket },
            connectingTimeoutNanoseconds: 180_000_000
        )

        viewModel.start()
        try? await Task.sleep(nanoseconds: 700_000_000)

        XCTAssertEqual(viewModel.connectionState, .degraded)
        XCTAssertEqual(socket.connectCallCount, 1)

        viewModel.retryLiveConnection()
        try? await Task.sleep(nanoseconds: 450_000_000)

        XCTAssertEqual(socket.connectCallCount, 2)
        XCTAssertNotEqual(viewModel.connectionState, .degraded)

        try? await Task.sleep(nanoseconds: 700_000_000)
        XCTAssertEqual(socket.connectCallCount, 2)

        viewModel.stop()
    }

    func testSimulatedCallerFlowStateProgressionAndEventEmission() async throws {
        let sessionService = MockTakeoverSessionService()
        let socket = MockSocketClient(scenarios: [.connectSuccess(eventsAfterConnect: [])])

        let session = ProtectionSession(
            sessionID: "fraus_test_session",
            callerNumber: "+19005550199",
            callerLabel: "Possible Bank Impersonation",
            callCategory: .scam,
            aiAgentName: "Fraus Sentinel v1",
            statusText: ProtectionConnectionState.prepared.fallbackStatusText,
            connectionState: .prepared,
            signedConversationURL: URL(string: "wss://example.com/signed")!,
            sourceCallSessionID: UUID(),
            sessionStartTime: Date(),
            transcriptNotes: ["Caller: This is your bank security unit."],
            scamIndicators: ["urgency pressure language"],
            extractedEntities: [SessionEntity(key: "phone_number", value: "+19005550199", confidence: 100)],
            businessIntelligenceSteps: ["Transcript captured"]
        )

        let viewModel = ActiveProtectionViewModel(
            session: session,
            sessionService: sessionService,
            liveSocketClientFactory: { _ in socket }
        )

        var observedStates: [ProtectionConnectionState] = [viewModel.connectionState]
        var cancellables = Set<AnyCancellable>()
        viewModel.$connectionState
            .sink { state in
                if observedStates.last != state {
                    observedStates.append(state)
                }
            }
            .store(in: &cancellables)

        viewModel.start()

        let timeoutNanos: UInt64 = 9_000_000_000
        let pollNanos: UInt64 = 100_000_000
        var waited: UInt64 = 0

        while viewModel.connectionState != .receivingAgentEvents && waited < timeoutNanos {
            try? await Task.sleep(nanoseconds: pollNanos)
            waited += pollNanos
        }

        try? await Task.sleep(nanoseconds: 1_500_000_000)

        viewModel.stop()

        let expectedPath: [ProtectionConnectionState] = [
            .prepared,
            .connecting,
            .live,
            .receivingAgentEvents,
        ]

        for expected in expectedPath {
            XCTAssertTrue(
                observedStates.contains(expected),
                "Missing expected state \(expected.rawValue). Observed: \(observedStates.map(\.rawValue).joined(separator: " -> "))"
            )
        }

        let postedTypes = sessionService.ingestedEvents.map(\.eventType)
        XCTAssertTrue(postedTypes.contains("connected"))
        XCTAssertTrue(postedTypes.contains("simulated_caller_flow_started"))
        XCTAssertTrue(postedTypes.contains("simulated_caller_turn"))
        XCTAssertTrue(postedTypes.contains("agent_response_fallback"))
    }

    func testTimelineReconcilesAgentPartialFinalAndCorrection() async throws {
        let sessionService = MockTakeoverSessionService()
        let socket = MockSocketClient(
            scenarios: [
                .connectSuccess(eventsAfterConnect: [
                    .userTranscript(text: "Caller: Verify your account now", eventID: "u1"),
                    .agentChatResponsePart(text: "I can", responseID: "a1"),
                    .agentChatResponsePart(text: "help you safely.", responseID: "a1"),
                    .agentResponse(text: "I can help you safely.", eventID: "a1"),
                    .agentResponseCorrection(text: "I can help you safely. Do not share OTP.", correctedEventID: "a1")
                ])
            ]
        )

        let session = ProtectionSession(
            sessionID: "fraus_test_session_2",
            callerNumber: "+19005550199",
            callerLabel: "Possible Bank Impersonation",
            callCategory: .scam,
            aiAgentName: "Fraus Sentinel v1",
            statusText: ProtectionConnectionState.prepared.fallbackStatusText,
            connectionState: .prepared,
            signedConversationURL: URL(string: "wss://example.com/signed")!,
            sourceCallSessionID: UUID(),
            sessionStartTime: Date(),
            transcriptNotes: [],
            scamIndicators: [],
            extractedEntities: [],
            businessIntelligenceSteps: []
        )

        let viewModel = ActiveProtectionViewModel(
            session: session,
            sessionService: sessionService,
            liveSocketClientFactory: { _ in socket }
        )

        viewModel.start()
        try? await Task.sleep(nanoseconds: 800_000_000)
        viewModel.stop()

        let callerMessages = viewModel.conversationTimeline.filter { $0.speaker == .caller }
        XCTAssertFalse(callerMessages.isEmpty)

        let aiMessages = viewModel.conversationTimeline.filter { $0.speaker == .frausAI }
        XCTAssertEqual(aiMessages.count, 1)

        let finalMessage = try XCTUnwrap(aiMessages.first)
        XCTAssertEqual(finalMessage.status, .corrected)
        XCTAssertEqual(finalMessage.text, "I can help you safely. Do not share OTP.")
        XCTAssertFalse(viewModel.conversationTimeline.contains(where: { $0.status == .fallback }))
    }
}

private final class MockSocketClient: ElevenLabsSocketClienting {
    enum ConnectScenario {
        case connectSuccess(eventsAfterConnect: [ElevenLabsSocketEvent])
        case stallConnecting
    }

    var onConnectionStateChange: ((ElevenLabsSocketConnectionState) -> Void)?
    var onEvent: ((ElevenLabsSocketEvent) -> Void)?

    private(set) var audioChunksSent: Int = 0
    private(set) var connectCallCount: Int = 0
    private var scenarios: [ConnectScenario]

    init(scenarios: [ConnectScenario] = [.connectSuccess(eventsAfterConnect: [])]) {
        self.scenarios = scenarios
    }

    func connect() {
        connectCallCount += 1
        let scenario = scenarios.isEmpty ? .stallConnecting : scenarios.removeFirst()

        onConnectionStateChange?(.connecting)

        switch scenario {
        case .connectSuccess(let eventsAfterConnect):
            onConnectionStateChange?(.connected)
            for event in eventsAfterConnect {
                onEvent?(event)
            }
        case .stallConnecting:
            break
        }
    }

    func sendAudioChunk(base64Chunk: String, sequence: Int, isFinal: Bool) {
        if !base64Chunk.isEmpty {
            audioChunksSent += 1
        }
    }

    func disconnect() {
        onConnectionStateChange?(.closed)
    }
}

private final class MockTakeoverSessionService: TakeoverSessionServicing {
    private(set) var ingestedEvents: [TakeoverSessionEventRequestPayload] = []

    func startTakeover(
        verificationResult: VerificationResult,
        demoCallSession: DemoCallSession?
    ) async throws -> ProtectionSession {
        throw NSError(domain: "unused", code: 0)
    }

    func fetchSession(
        sessionID: String,
        callCategory: DemoCallCategory?,
        sourceCallSessionID: UUID?,
        sessionStartTime: Date,
        fallbackSession: ProtectionSession?
    ) async throws -> ProtectionSession {
        if let fallbackSession {
            return fallbackSession
        }
        throw NSError(domain: "missingFallback", code: 1)
    }

    func ingestEvent(
        sessionID: String,
        payload: TakeoverSessionEventRequestPayload
    ) async throws {
        ingestedEvents.append(payload)
    }
}
