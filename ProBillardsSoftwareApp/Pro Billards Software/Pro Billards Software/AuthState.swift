//
//  AuthState.swift
//  Pro Billards Software
//

import Foundation
import Combine

final class AuthState: ObservableObject {
    static let shared = AuthState()

    /// True if we have a saved token (user is "logged in" for this session).
    @Published private(set) var isLoggedIn: Bool = false

    private init() {
        // Don't call Keychain from init (avoids concurrency / isolation issues).
        // Call checkLoggedIn() from ContentView.onAppear instead.
    }

    /// Call on launch and after login/logout to update isLoggedIn.
    func checkLoggedIn() {
        isLoggedIn = KeychainHelper.loadToken() != nil
    }

    /// Call after successful login (saves token and updates state).
    func didLogin(token: String) {
        KeychainHelper.saveToken(token)
        isLoggedIn = true
    }

    /// Call on logout (removes token and updates state).
    func logout() {
        KeychainHelper.deleteToken()
        isLoggedIn = false
    }
}
