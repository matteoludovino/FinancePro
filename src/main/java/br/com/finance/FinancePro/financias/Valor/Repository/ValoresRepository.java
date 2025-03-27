package br.com.finance.FinancePro.financias.Valor.Repository;

import br.com.finance.FinancePro.financias.Valor.Model.ValoresModel;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ValoresRepository extends JpaRepository<ValoresModel, Long> {
}
