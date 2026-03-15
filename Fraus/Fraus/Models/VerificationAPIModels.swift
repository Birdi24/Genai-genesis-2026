import Foundation

struct VerifyNumberRequest: Codable {
    let phoneNumber: String

    enum CodingKeys: String, CodingKey {
        case phoneNumber = "phone_number"
    }
}

enum VerifyBackendStatus: String, Codable {
    case verified
    case scam
    case unknown
}

struct VerifyNumberResponse: Codable {
    let phoneNumber: String
    let status: VerifyBackendStatus
    let reason: String
    let threatTags: [String]
    let sourceLabel: String?
    let riskLevel: String?
}

extension VerifyNumberResponse {
    func toVerificationResult() -> VerificationResult {
        let mappedState: VerificationState
        switch status {
        case .verified:
            mappedState = .verified
        case .scam:
            mappedState = .suspicious
        case .unknown:
            mappedState = .unknown
        }

        let tags = (threatTags.isEmpty ? [defaultTag(for: status)] : threatTags).map {
            ThreatTag(label: $0, severity: severity(for: $0, status: status, riskLevel: riskLevel))
        }

        return VerificationResult(
            phoneNumber: phoneNumber,
            state: mappedState,
            explanation: reason,
            threatTags: tags,
            confidence: nil,
            sourceLabel: sourceLabel,
            riskLevel: riskLevel
        )
    }

    private func defaultTag(for status: VerifyBackendStatus) -> String {
        switch status {
        case .verified:
            return "Known Contact"
        case .scam:
            return "Potential Scam"
        case .unknown:
            return "Unknown Caller"
        }
    }

    private func severity(for tag: String, status: VerifyBackendStatus, riskLevel: String?) -> ThreatSeverity {
        let tagValue = tag.lowercased()
        let riskValue = (riskLevel ?? "").lowercased()

        if status == .scam || riskValue == "high" || riskValue == "critical" {
            return .high
        }
        if riskValue == "medium" || tagValue.contains("unknown") || tagValue.contains("no trust") {
            return .medium
        }
        return .low
    }
}
