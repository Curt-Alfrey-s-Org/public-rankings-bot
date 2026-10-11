//
//  ContentView.swift
//  Pro Billards Software
//
//  Created by Nickey Example on 3/11/26.
//

import SwiftUI

struct ContentView: View {
    @ObservedObject private var auth = AuthState.shared

    var body: some View {
        Group {
            if auth.isLoggedIn {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .onAppear { auth.checkLoggedIn() }
    }
}

#Preview {
    ContentView()
}
