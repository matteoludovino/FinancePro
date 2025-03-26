package br.com.finance.FinancePro.financias.Transacoes.Repository;

import br.com.finance.FinancePro.financias.Transacoes.Model.TransacaoModel;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TransacaoRepository extends JpaRepository<TransacaoModel, Long> {
}
