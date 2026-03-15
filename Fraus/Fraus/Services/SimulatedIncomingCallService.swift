import Foundation

protocol SimulatedIncomingCallServicing {
    func demoIncomingCalls() -> [DemoCallSession]
}

struct SimulatedIncomingCallService: SimulatedIncomingCallServicing {
    func demoIncomingCalls() -> [DemoCallSession] {
        [
            DemoCallSession(
                phoneNumber: "+1 (900) 555-0199",
                callerLabel: "Possible Bank Impersonation",
                callCategory: .scam,
                status: .incoming,
                transcriptLines: [
                    "Caller: This is your bank security unit.",
                    "Caller: We detected suspicious transfers and need urgent verification.",
                    "Caller: Share your OTP immediately to secure your account."
                ],
                transferredToAI: false,
                startTime: Date()
            ),
            DemoCallSession(
                phoneNumber: "+1 (312) 000-0000",
                callerLabel: "Unknown Account Desk",
                callCategory: .unknown,
                status: .incoming,
                transcriptLines: [
                    "Caller: Hi, this is account support.",
                    "Caller: We need to confirm your account quickly.",
                    "Caller: Please provide the one-time code sent to your phone."
                ],
                transferredToAI: false,
                startTime: Date()
            )
        ]
    }
}
