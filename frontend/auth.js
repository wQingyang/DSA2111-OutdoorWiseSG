(() => {
  async function authRequest(path, options = {}) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw Error(typeof data?.detail === 'string' ? data.detail : 'Request failed.');
    return data;
  }
  window.outdoorwiseAuth = { request: authRequest };
  const form = document.getElementById('register-form');
  if (form) {
    const message = document.getElementById('auth-message');
    const check = async () => { try { const data = await authRequest(`/api/auth/username-availability?username=${encodeURIComponent(form.username.value)}`); message.textContent = data.available ? 'Username available' : 'Username already exists'; message.className = `auth-message ${data.available ? 'success' : 'error'}`; } catch (e) { message.textContent = e.message; message.className = 'auth-message error'; } };
    form.username.addEventListener('blur', check);
    form.addEventListener('submit', async event => { event.preventDefault(); message.textContent = ''; if (form.password.value !== form.confirm_password.value) { message.textContent = 'Passwords do not match.'; message.className = 'auth-message error'; return; } try { await authRequest('/api/auth/register', { method: 'POST', body: JSON.stringify({ username: form.username.value, password: form.password.value }) }); location.href = '/profile.html'; } catch (e) { message.textContent = e.message; message.className = 'auth-message error'; } });
  }
  const login = document.getElementById('login-form');
  if (login) login.addEventListener('submit', async event => { event.preventDefault(); const message = document.getElementById('auth-message'); try { await authRequest('/api/auth/login', { method: 'POST', body: JSON.stringify({ username: login.username.value, password: login.password.value }) }); location.href = '/profile.html'; } catch (e) { message.textContent = e.message; message.className = 'auth-message error'; } });
})();
