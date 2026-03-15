import Foundation
import Combine

@MainActor
final class VerifyCallerViewModel: ObservableObject {
    @Published var phoneNumber: String = ""
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    private let verificationService: VerificationServicing

    init(
        initialPhoneNumber: String? = nil,
        verificationService: VerificationServicing? = nil
    ) {
        self.verificationService = verificationService ?? VerificationAPIService()
        self.phoneNumber = initialPhoneNumber ?? ""
    }

    var canSubmit: Bool {
        !phoneNumber.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }

    func setPhoneNumber(_ value: String) {
        phoneNumber = value
        errorMessage = nil
    }

    func clearPhoneNumber() {
        phoneNumber = ""
        errorMessage = nil
    }

    func verifyNumber(onSuccess: @escaping (VerificationResult) -> Void) {
        guard canSubmit else { return }

        let request = VerifyNumberRequest(phoneNumber: phoneNumber)
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let response = try await verificationService.verifyNumber(request)
                let result = response.toVerificationResult()
                isLoading = false
                onSuccess(result)
            } catch {
                isLoading = false
                if let localizedError = error as? LocalizedError,
                   let message = localizedError.errorDescription {
                    errorMessage = message
                } else {
                    errorMessage = "Unable to verify this number right now. Please try again."
                }
            }
        }
    }
}
