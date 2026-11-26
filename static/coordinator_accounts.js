'use strict';
// Dedicated create-only form. Permission and student role are enforced server-side.
const coordinatorAccountsBeforeCreate = coordinatorView;
coordinatorView = function () {
  const previous = coordinatorAccountsBeforeCreate();
  const entry = `<section class="card"><h2>Cadastrar um aluno</h2><p>Crie o acesso com nome, login e senha provisória. A nova conta será do tipo <strong>Aluno</strong>, com acesso somente ao próprio planejamento e desempenho.</p>${button('Cadastrar aluno','coordinator-new-student','primary')}<p class="micro">O aluno deverá trocar a senha no primeiro acesso. Perfis de coordenador, especial e Master, redefinição de senhas e mudanças de acesso continuam sob responsabilidade do Master.</p></section>`;
  return previous.replace('<section class="card">', entry + '<section class="card">');
};
acts['coordinator-new-student'] = () => {
  if (ME?.role !== 'coordenador') throw new Error('Utilize o painel correspondente ao seu perfil.');
  if (!safeLeave()) return;
  modalForm('Cadastrar aluno', `<div class="notice">Perfil fixo: <strong>Aluno</strong>. Troca de senha obrigatória no primeiro acesso.</div><div class="form-grid">${input('Nome completo','name','','text','required maxlength="150" autocomplete="off"')}${input('Login do aluno','username','','text','required minlength="3" maxlength="40" pattern="[A-Za-z0-9_.-]{3,40}" autocapitalize="none" spellcheck="false" autocomplete="off"')}${input('Senha provisória','password','','password','required minlength="8" maxlength="128" autocomplete="new-password"')}</div><p class="micro">Login: letras sem acento, números, ponto, hífen ou sublinhado. Senha: de 8 a 128 caracteres. Informe o acesso ao aluno por um canal privado; a senha não será exibida depois de salva.</p>`, async (form, data) => {
    const history=await historyForNewStudent(data.name);
    const created = await api('/api/coordinator/accounts', {
      name: data.name, username: data.username, password: data.password, role: 'aluno', ...history
    });
    form.elements.password.value = '';
    dirty = false;
    try {
      await refreshAccounts();
      await load();
      toast('Aluno cadastrado. Login: ' + created.username + '. A troca de senha será exigida no primeiro acesso.');
    } catch (_) {
      // The creation already committed; do not invite the user to submit twice.
      toast('Aluno cadastrado com login ' + created.username + '. Recarregue a página para atualizar a lista.');
    }
  }, 'Cadastrar aluno');
};
