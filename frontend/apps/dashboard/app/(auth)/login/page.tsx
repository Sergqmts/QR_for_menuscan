import LoginForm from "./login-form";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-orange-500">MenuScan</h1>
          <p className="text-gray-500 text-sm mt-1">Войдите в личный кабинет</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
