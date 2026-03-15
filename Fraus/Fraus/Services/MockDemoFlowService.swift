import Foundation

struct MockVerificationService {
    static let verifiedNumbers: [String: String] = [
        "18005551234": "Chase Bank — Official",
        "18004567890": "Bank of America — Fraud Dept",
        "18009221111": "Wells Fargo — Customer Service",
    ]

    func verify(phoneNumber: String) -> VerificationResult {
        let normalizedDigits = phoneNumber.filter(\.isNumber)
        let formattedNumber = normalizedDigits.isEmpty ? phoneNumber : normalizedDigits

        if let bankName = Self.verifiedNumbers[normalizedDigits] {
            return VerificationResult(
                phoneNumber: formattedNumber,
                state: .verified,
                explanation: "This is a verified institutional number for \(bankName). No AI takeover needed.",
                threatTags: [
                    ThreatTag(label: "Verified Institution", severity: .low),
                    ThreatTag(label: "Known Contact", severity: .low),
                    ThreatTag(label: "No Pressure Language", severity: .low)
                ],
                confidence: 99,
                sourceLabel: "Fraus Verified Directory",
                riskLevel: "low"
            )
        }

        if normalizedDigits.hasSuffix("1111") {
            return VerificationResult(
                phoneNumber: formattedNumber,
                state: .verified,
                explanation: "This caller matches trusted behavior and known identity patterns.",
                threatTags: [
                    ThreatTag(label: "Known Contact", severity: .low),
                    ThreatTag(label: "No Pressure Language", severity: .low)
                ],
                confidence: 92,
                sourceLabel: "Fraus Verification Engine",
                riskLevel: "low"
            )
        }

        if normalizedDigits.hasSuffix("9999") {
            return VerificationResult(
                phoneNumber: formattedNumber,
                state: .suspicious,
                explanation: "High-risk social engineering traits detected in caller profile and behavior fingerprint.",
                threatTags: [
                    ThreatTag(label: "Impersonation Risk", severity: .high),
                    ThreatTag(label: "Urgency Pressure", severity: .high),
                    ThreatTag(label: "OTP Request Pattern", severity: .high)
                ],
                confidence: 88,
                sourceLabel: "Fraus Verification Engine",
                riskLevel: "high"
            )
        }

        return VerificationResult(
            phoneNumber: formattedNumber,
            state: .unknown,
            explanation: "Insufficient trust signals. Caller identity is not yet validated in the network.",
            threatTags: [
                ThreatTag(label: "No Trust History", severity: .medium),
                ThreatTag(label: "Intent Unclear", severity: .medium)
            ],
            confidence: 63,
            sourceLabel: "Fraus Verification Engine",
            riskLevel: "medium"
        )
    }
}

struct MockProtectionSessionFactory {
    func makeSession(
        for result: VerificationResult,
        callSession: DemoCallSession? = nil,
        sessionID: String? = nil
    ) -> ProtectionSession {
        let callNotes = callSession?.transcriptLines ?? []

        return ProtectionSession(
            sessionID: sessionID,
            callerNumber: result.phoneNumber,
            callerLabel: callSession?.callerLabel,
            callCategory: callSession?.callCategory,
            aiAgentName: "Fraus Sentinel v1",
            statusText: "AI actively containing caller",
            connectionState: .degraded,
            signedConversationURL: nil,
            sourceCallSessionID: callSession?.id,
            sessionStartTime: callSession?.startTime ?? Date(),
            transcriptNotes: [
                "Caller claims to be from customer bank security.",
                "Urgency pressure detected: 'Act in 5 minutes or account will be frozen'.",
                "Caller asks for one-time password and card verification code.",
                "AI agent redirects request and requests institutional verification.",
                "Caller provides inconsistent identity details across prompts."
            ] + callNotes,
            scamIndicators: [
                "Bank impersonation script",
                "OTP extraction attempt",
                "Artificial urgency pressure",
                "Identity mismatch across responses"
            ],
            extractedEntities: [
                SessionEntity(key: "Claimed Employee ID", value: "BK-4471", confidence: 76),
                SessionEntity(key: "Requested OTP", value: "6-digit SMS code", confidence: 95),
                SessionEntity(key: "Payment Destination", value: "acct-x9-72-004", confidence: 81),
                SessionEntity(key: "Claimed Department", value: "Fraud Desk", confidence: 58)
            ],
            businessIntelligenceSteps: [
                "Transcript captured",
                "Entities extracted",
                "Fraud analysis queued",
                "Fraud graph update pending"
            ]
        )
    }
}
