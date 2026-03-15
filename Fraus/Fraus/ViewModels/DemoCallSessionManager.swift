import Foundation
import Combine

@MainActor
final class DemoCallSessionManager: ObservableObject {
    @Published private(set) var activeSession: DemoCallSession?

    func beginSession(from template: DemoCallSession) {
        activeSession = DemoCallSession(
            id: UUID(),
            phoneNumber: template.phoneNumber,
            callerLabel: template.callerLabel,
            callCategory: template.callCategory,
            status: .incoming,
            transcriptLines: template.transcriptLines,
            transferredToAI: false,
            startTime: Date()
        )
    }

    func markVerifying() {
        guard let activeSession else { return }
        self.activeSession = activeSession.updating(status: .verifying)
    }

    func applyVerificationResult(_ result: VerificationResult) {
        guard let activeSession else { return }

        switch result.state {
        case .verified:
            self.activeSession = activeSession.updating(status: .verified)
        case .suspicious, .unknown:
            self.activeSession = activeSession.updating(status: .suspicious)
        }
    }

    func markTransferred() {
        guard let activeSession else { return }
        self.activeSession = activeSession.updating(status: .transferred, transferredToAI: true)
    }

    func markActiveProtection() {
        guard let activeSession else { return }
        self.activeSession = activeSession.updating(status: .activeProtection, transferredToAI: true)
    }

    func markCompleted() {
        guard let activeSession else { return }
        self.activeSession = activeSession.updating(status: .completed)
    }

    func clear() {
        activeSession = nil
    }
}
