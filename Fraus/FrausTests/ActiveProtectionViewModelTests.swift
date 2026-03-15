import XCTest
import Combine
@testable import Fraus

@MainActor
final class ActiveProtectionViewModelTests: XCTestCase {
    func testConnectionStateProgressesThroughExpectedPhases() async throws {
        let session = makeSession()
        let viewModel = ActiveProtectionViewModel(session: session)

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

        let timeoutNanos: UInt64 = 8_000_000_000
        let pollNanos: UInt64 = 100_000_000
        var waited: UInt64 = 0

        while viewModel.connectionState != .receivingAgentEvents && waited < timeoutNanos {
            try? await Task.sleep(nanoseconds: pollNanos)
            waited += pollNanos
        }

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
    }

    func testConversationTimelinePopulatesWithCallerAndAIMessages() async throws {
        let session = makeSession()
        let viewModel = ActiveProtectionViewModel(session: session)

        viewModel.start()
        try? await Task.sleep(nanoseconds: 6_000_000_000)
        viewModel.stop()

        XCTAssertFalse(viewModel.conversationTimeline.isEmpty)

        let callerMessages = viewModel.conversationTimeline.filter { $0.speaker == .caller }
        let aiMessages = viewModel.conversationTimeline.filter { $0.speaker == .frausAI }

        XCTAssertGreaterThanOrEqual(callerMessages.count, 1)
        XCTAssertGreaterThanOrEqual(aiMessages.count, 1)
    }

    func testScamIndicatorsAppearDuringConversation() async throws {
        let session = makeSession(scamIndicators: [
            "Bank impersonation script",
            "OTP extraction attempt"
        ])
        let viewModel = ActiveProtectionViewModel(session: session)

        viewModel.start()
        try? await Task.sleep(nanoseconds: 8_000_000_000)
        viewModel.stop()

        XCTAssertGreaterThanOrEqual(viewModel.scamIndicators.count, 1)
    }

    func testTimerIncrementsElapsedSeconds() async throws {
        let session = makeSession()
        let viewModel = ActiveProtectionViewModel(session: session)

        viewModel.start()
        try? await Task.sleep(nanoseconds: 2_500_000_000)
        viewModel.stop()

        XCTAssertGreaterThanOrEqual(viewModel.elapsedSeconds, 2)
    }

    func testStopCancelsAllTasks() async throws {
        let session = makeSession()
        let viewModel = ActiveProtectionViewModel(session: session)

        viewModel.start()
        try? await Task.sleep(nanoseconds: 500_000_000)
        viewModel.stop()

        let timelineCount = viewModel.conversationTimeline.count
        try? await Task.sleep(nanoseconds: 2_000_000_000)

        XCTAssertEqual(viewModel.conversationTimeline.count, timelineCount)
    }

    private func makeSession(
        scamIndicators: [String] = ["Bank impersonation script", "OTP extraction attempt", "Artificial urgency pressure"],
        extractedEntities: [SessionEntity] = [
            SessionEntity(key: "Claimed Employee ID", value: "BK-4471", confidence: 76),
            SessionEntity(key: "Requested OTP", value: "6-digit SMS code", confidence: 95)
        ]
    ) -> ProtectionSession {
        ProtectionSession(
            sessionID: nil,
            callerNumber: "+19005550199",
            callerLabel: "Possible Bank Impersonation",
            callCategory: .scam,
            aiAgentName: "Fraus Sentinel v1",
            statusText: ProtectionConnectionState.prepared.fallbackStatusText,
            connectionState: .prepared,
            signedConversationURL: nil,
            sourceCallSessionID: nil,
            sessionStartTime: Date(),
            transcriptNotes: [],
            scamIndicators: scamIndicators,
            extractedEntities: extractedEntities,
            businessIntelligenceSteps: ["Transcript captured", "Entities extracted"]
        )
    }
}
